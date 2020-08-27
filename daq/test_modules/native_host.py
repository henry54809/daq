"""A docker-based mininet host"""
import os
from subprocess import PIPE, STDOUT

# pylint: disable=import-error
# pylint: disable=no-name-in-module
from mininet.log import error, debug
from mininet.node import Host
from mininet.util import quietRun, errRun

from clib.mininet_test_util import DEVNULL

DEFAULT_PREFIX = 'mininet'
STARTUP_TIMEOUT_MS = 20000

class NativeHost(Host):
    """Mininet host that encapsulates a shell"""

    # pylint: disable=too-many-arguments
    def __init__(self, name, basedir=None, tmpdir=None, env_vars=None, vol_maps=None,
                 startup_script='entrypoint', **kwargs):
        self.basedir = basedir
        self.tmpdir = tmpdir
        self.env_vars = env_vars if env_vars is not None else []
        self.vol_maps = vol_maps if vol_maps is not None else []
        self.name = name
        self.startup_script = os.path.join(self.basedir, startup_script)
        self.active_pipe = None
        self.active_log = None
        Host.__init__(self, name, **kwargs)

    def open_log(self, log_name='activate.log'):
        """Open a log file for writing and return it."""
        return open(os.path.join(self.tmpdir, log_name), 'w')

    def activate(self, log_name='activate.log'):
        """Active a container and return STDOUT to it."""
        assert not self.active_pipe, '%s already activated' % self.name

        for env_var in self.env_vars:
            self.cmd('export %s="%s"' % env_var)

        self.cmd('mkdir %s' % os.path.join(self.basedir, "config"))

        for vol_map in self.vol_maps:
            self.cmd('ln -s %s %s' % vol_map)

        if log_name:
            stdout = self.open_log(log_name)
            self.active_log = stdout
        else:
            stdout = PIPE
            self.active_log = None

        self.active_pipe = self.popen(self.startup_script, stdin=DEVNULL, stdout=stdout,
                                      stderr=STDOUT)
        pipe_out = self.active_pipe.stdout
        out_fd = pipe_out.fileno() if pipe_out else None
        debug('Active_pipe container pid %s fd %s' %
              (self.active_pipe.pid, out_fd))
        return self.active_pipe

    def terminate(self):
        """Override Mininet terminate() to partially avoid pty leak."""
        for vol_map in self.vol_maps:
            self.cmd('rm -r %s' % vol_map[1])
        self.cmd('rm -r %s' % os.path.join(self.basedir, 'config'))

        super().terminate()
        debug('Terminating container shell %s, pipe %s' % (
            self.shell, self.active_pipe))
        if self.active_pipe:
            if self.active_pipe.stdout:
                self.active_pipe.stdout.close()
            if self.active_pipe.returncode is None:
                self.active_pipe.kill()
                self.active_pipe.poll()
            active_pipe_returncode = self.active_pipe.returncode
            self.active_pipe = None
            if self.active_log:
                self.active_log.close()
                self.active_log = None
            return active_pipe_returncode
        return None

def make_native_host(basedir, startup_script):
    """Utility function to create a native-host class that can be passed to mininet"""

    class _NativeHost(NativeHost):
        """Internal class that represents a native host"""

        def __init__(self, *args, **kwargs):
            host_name = args[0]
            assert kwargs['tmpdir'], 'tmpdir required for docker host'
            kwargs['tmpdir'] = os.path.join(kwargs['tmpdir'], host_name)
            kwargs['basedir'] = basedir
            kwargs['startup_script'] = startup_script
            super(_NativeHost, self).__init__(*args, **kwargs)

    return _NativeHost
