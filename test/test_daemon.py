import os
import time
import pickle
import shutil
import unittest
import subprocess

from daemonize import Daemonize

from pueue.daemon.daemon import Daemon
from pueue.helper.socket import getClientSocket
from pueue.helper.files import createDir

from pueue.subcommands.daemonStates import daemonState
from pueue.subcommands.queueDisplaying import executeStatus
from pueue.subcommands.queueManipulation import executeAdd, executeRemove, executeSwitch


class DaemonTesting(unittest.TestCase):
    def setUp(self):
        queue = createDir()+'/queue'
        if os.path.exists(queue):
            os.remove(queue)

        process = subprocess.Popen(
                'pueue --daemon',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
        )
        output, error = process.communicate()

    def tearDown(self):
        args = {}
        daemonState('STOPDAEMON')(args)

    def sendCommand(self, command):
        client = getClientSocket()
        client.send(pickle.dumps(command, -1))
        answer = client.recv(8192)
        response = pickle.loads(answer)
        client.close()
        return response

    def getStatus(self):
        status = self.sendCommand({'mode': 'status'})
        return status

    def test_pause(self):
        status = self.getStatus()
        self.assertEqual(status['status'], 'running')
        daemonState('pause')({})
        status = self.getStatus()
        self.assertEqual(status['status'], 'paused')

    def test_start(self):
        daemonState('pause')({})
        daemonState('start')({})
        status = self.getStatus()
        self.assertEqual(status['status'], 'running')

    def test_add(self):
        daemonState('pause')({})
        response = self.sendCommand({'mode':'add', 'command': 'ls', 'path': '/tmp'})
        self.assertEqual(response['status'],'success')
        status = self.getStatus()
        self.assertEqual(status['data'][0]['command'], 'ls')
        self.assertEqual(status['data'][0]['path'], '/tmp')


    def test_remove_fails(self):
        response = self.sendCommand({'mode':'remove', 'key': 0})
        self.assertEqual(response['status'],'error')

    def test_remove_running(self):
        executeAdd({'command': 'sleep 60'})
        response = self.sendCommand({'mode':'remove', 'key': 0})
        self.assertEqual(response['status'],'error')

    def test_remove(self):
        daemonState('pause')({})
        status = self.getStatus()
        self.assertEqual(status['status'], 'paused')
        executeAdd({'command': 'ls'})

        response = self.sendCommand({'mode':'remove', 'key': 0})
        print(response['message'])
        self.assertEqual(response['status'],'success')
        status = self.getStatus()
        self.assertFalse('0' in status['data'])

    def test_switch(self):
        daemonState('pause')({})
        executeAdd({'command': 'ls'})
        executeAdd({'command': 'ls -l'})
        executeSwitch({'first': 0, 'second': 1})
        status = self.getStatus()
        self.assertEqual(status['data'][0]['command'], 'ls -l')
        self.assertEqual(status['data'][1]['command'], 'ls')

    def test_switch_fails(self):
        response = self.sendCommand({'mode': 'switch', 'first': 0, 'second': 1})
        self.assertEqual(response['status'],'error')

    def test_switch_running(self):
        executeAdd({'command': 'sleep 60'})
        executeAdd({'command': 'ls -l'})
        response = self.sendCommand({'mode': 'switch', 'first': 0, 'second': 1})
        self.assertEqual(response['status'],'error')

    def test_kill(self):
        executeAdd({'command': 'sleep 60'})
        daemonState('kill')({})
        status = self.getStatus()
        self.assertEqual(status['status'], 'paused')
        self.assertEqual(status['process'], 'No process')

    def test_stop(self):
        executeAdd({'command': 'sleep 60'})
        daemonState('stop')({})
        status = self.getStatus()
        self.assertEqual(status['status'], 'paused')
        self.assertEqual(status['process'], 'No process')

    def test_process(self):
        executeAdd({'command': 'sleep 60'})
        status = self.getStatus()
        self.assertEqual(status['status'], 'running')
        self.assertEqual(status['process'], 'running')

    def test_process(self):
        daemonState('pause')({})
        executeAdd({'command': 'sleep 60'})
        executeAdd({'command': 'sleep 60'})
        daemonState('reset')({})
        status = self.getStatus()
        self.assertEqual(status['status'], 'paused')
        self.assertEqual(status['data'], 'Queue is empty')
