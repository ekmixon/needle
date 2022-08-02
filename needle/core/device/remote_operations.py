import os
import time
import threading
import subprocess

from ..utils.constants import Constants
from ..utils.utils import Utils


class RemoteOperations(object):
    # ==================================================================================================================
    # INIT
    # ==================================================================================================================
    def __init__(self, device):
        self._device = device

    # ==================================================================================================================
    # FILES
    # ==================================================================================================================
    def file_exist(self, path):
        path = Utils.escape_path(path)
        cmd = 'if [ -f %s ]; then echo "yes"; else echo "no" ; fi' % path
        out = self.command_blocking(cmd, internal=True)
        res = out[0] if type(out) is list else out
        return res.strip() == "yes"

    def file_create(self, path):
        path = Utils.escape_path(path)
        if not self.file_exist(path):
            cmd = f'touch {path}'
            self.command_blocking(cmd)

    def file_delete(self, path):
        path = Utils.escape_path(path)
        if self.file_exist(path):
            cmd = f'rm {path} 2> /dev/null'
            self.command_blocking(cmd)

    def file_copy(self, src, dst):
        src, dst = Utils.escape_path(src), Utils.escape_path(dst)
        cmd = f"cp {src} {dst}"
        self.command_blocking(cmd)

    def file_move(self, src, dst):
        src, dst = Utils.escape_path(src), Utils.escape_path(dst)
        cmd = f"mv {src} {dst}"
        self.command_blocking(cmd)

    # ==================================================================================================================
    # DIRECTORIES
    # ==================================================================================================================
    def dir_exist(self, path):
        path = Utils.escape_path(path)
        cmd = 'if [ -d %s ]; then echo "yes"; else echo "no" ; fi' % path
        out = self.command_blocking(cmd, internal=True)
        res = out[0] if type(out) is list else out
        return res.strip() == "yes"

    def dir_create(self, path):
        path = Utils.escape_path(path)
        if not self.dir_exist(path):
            cmd = f'mkdir {path}'
            self.command_blocking(cmd)

    def dir_delete(self, path, force=False):
        def delete(path):
            cmd = f'rm -rf {path} 2> /dev/null'
            self.command_blocking(cmd)

        path = Utils.escape_path(path)
        if force: delete(path)
        elif self.dir_exist(path): delete(path)

    def dir_list(self, path, recursive=False):
        if not self.dir_exist(path):
            return None
        path = Utils.escape_path(path)
        opts = '-aR' if recursive else ''
        cmd = 'ls {opts} {path}'.format(opts=opts, path=path)
        file_list = self.command_blocking(cmd)
        return map(lambda x: x.strip(), file_list)

    def dir_reset(self, path):
        if self.dir_exist(path): self.dir_delete(path)
        self.dir_create(path)

    # ==================================================================================================================
    # COMMANDS
    # ==================================================================================================================
    def command_blocking(self, cmd, internal=True):
        """Run a blocking command: wait for its completion before resuming execution."""
        self._device.printer.debug(f'[REMOTE CMD] Remote Command: {cmd}')
        out, err = self._device._exec_command_ssh(cmd, internal)
        if type(out) is tuple: out = out[0]
        return out

    def command_interactive(self, cmd):
        """Run a command which requires an interactive shell."""
        self._device.printer.debug(f"[REMOTE CMD] Remote Interactive Command: {cmd}")
        cmd = 'sshpass -p "{password}" ssh {hostverification} -p {port} -t {username}@{ip} "{cmd}"'.format(password=self._device._password,
                                                                                                           hostverification=Constants.DISABLE_HOST_VERIFICATION,
                                                                                                           port=self._device._port,
                                                                                                           username=self._device._username,
                                                                                                           ip=self._device._ip,
                                                                                                           cmd=cmd)
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        stdout, stderr = proc.stdout.read(), proc.stderr.read()
        return stdout, stderr

    def command_interactive_tty(self, cmd):
        """Run a command in a full TTY shell."""
        self._device.printer.debug(
            f"[REMOTE CMD] Remote Interactive TTY Command: {cmd}"
        )

        cmd = 'sshpass -p "{password}" ssh {hostverification} -p {port} -t {username}@{ip} "{cmd}"'.format(password=self._device._password,
                                                                                                           hostverification=Constants.DISABLE_HOST_VERIFICATION,
                                                                                                           port=self._device._port,
                                                                                                           username=self._device._username,
                                                                                                           ip=self._device._ip,
                                                                                                           cmd=cmd)
        return subprocess.call(cmd, shell=True)

    def command_background_start(self, module, cmd):
        """Run a background command: run it in a new thread and resume execution immediately."""
        self._device.printer.debug(f'[REMOTE CMD] Remote Background Command: {cmd}')

        def daemon(module, cmd):
            """Daemon used to run the command so to avoid blocking the UI"""
            # Run command
            cmd += ' & echo $!'
            out = self.command_blocking(cmd)
            # Parse PID of the process
            try:
                pid = out[0].strip()
            except Exception as e:
                module.printer.error("Error while parsing process PID. Skipping")
                pid = None
            module.PID = pid
            module.printer.info("Monitoring in background...Kill this process when you want to see the dumped content")

        # Run command in a thread
        d = threading.Thread(name='daemon', target=daemon, args=(module, cmd))
        d.setDaemon(True)
        d.start()
        time.sleep(2)

    def command_background_stop(self, pid):
        """Stop a running background command."""
        self._device.printer.debug(
            f'[REMOTE CMD] Stopping Remote Background Command [pid: {pid}]'
        )

        cmd = f"kill {pid}"
        self.command_blocking(cmd)

    def kill_proc(self, procname):
        """Kill the running process with the specified name."""
        self._device.printer.debug(f'[REMOTE CMD] Killing process [name: {procname}]')
        cmd = 'killall -9 "%s"' % procname
        self.command_blocking(cmd)

    # ==================================================================================================================
    # DOWNLOAD/UPLOAD
    # ==================================================================================================================
    def download(self, src, dst, recursive=False):
        """Download a file from the device."""
        src, dst = Utils.escape_path_scp(src), Utils.escape_path(dst)
        self._device.printer.debug(f"Downloading: {src} -> {dst}")

        cmd = 'sshpass -p "{password}" scp {hostverification} -P {port}'.format(password=self._device._password,
                                                                                hostverification=Constants.DISABLE_HOST_VERIFICATION,
                                                                                port=self._device._port)
        if recursive: cmd += ' -r'
        cmd += ' {username}@{ip}:{src} {dst}'.format(username=self._device._username,
                                                    ip=self._device._ip,
                                                    src=src, dst=dst)

        self._device.local_op.command_blocking(cmd)

    def upload(self, src, dst, recursive=True):
        """Upload a file on the device."""
        src, dst = Utils.escape_path_scp(src), Utils.escape_path_scp(dst)
        self._device.printer.debug(f"Uploading: {src} -> {dst}")

        cmd = 'sshpass -p "{password}" scp {hostverification} -P {port}'.format(password=self._device._password,
                                                                                hostverification=Constants.DISABLE_HOST_VERIFICATION,
                                                                                port=self._device._port)
        if recursive: cmd += ' -r'
        cmd += ' {src} {username}@{ip}:{dst}'.format(src=src,
                                                    username=self._device._username,
                                                    ip=self._device._ip,
                                                    dst=dst)

        self._device.local_op.command_blocking(cmd)

    # ==================================================================================================================
    # FILE SPECIFIC
    # ==================================================================================================================
    def build_temp_path_for_file(self, fname):
        """Given a filename, returns the full path for the filename in the device's temp folder."""
        return os.path.join(self._device.TEMP_FOLDER, Utils.extract_filename_from_path(fname))

    def create_timestamp_file(self, fname):
        """Create a file with the current time of last modification, to be used as a reference."""
        ts = self.build_temp_path_for_file(fname)
        cmd = f'touch {ts}'
        self.command_blocking(cmd)
        return ts

    def chmod_x(self, fname):
        """Chmod +x the provided path."""
        cmd = f'chmod +x {fname}'
        self.command_blocking(cmd)

    def parse_plist(self, plist):
        """Given a plist file, copy it to temp folder and parse it."""
        # Get a copy of the plist
        plist_copy = self._device.local_op.build_temp_path_for_file('plist', None, path=Constants.FOLDER_TEMP)
        self._device.printer.debug(
            f'Copying the plist to temp: {plist} -> {plist_copy}'
        )

        self._device.pull(plist, plist_copy)
        return Utils.plist_read_from_file(plist_copy)

    def read_file(self, fname, grep_args=None):
        """Given a filename, prints its content on screen."""
        if not self.file_exist(fname):
            self._device.printer.error(f'File not found: {fname}')
            return
        cmd = 'cat {fname}'.format(fname=fname)
        if grep_args:
            cmd += ' | grep {grep_args}'.format(grep_args=grep_args)
        return self.command_blocking(cmd, internal=True)

    def write_file(self, fname, body):
        """Given a filename, write body into it"""
        cmd = "echo \"{content}\" > {dst}".format(content=body, dst=fname)
        self.command_blocking(cmd)
