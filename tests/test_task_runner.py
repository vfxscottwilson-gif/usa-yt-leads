import os
import subprocess
import sys
import unittest
from unittest.mock import patch
from src.task_runner import run_browser_task

class HardTimeoutTests(unittest.TestCase):
    def test_deadline_terminates_real_worker(self):
        options={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW}
        process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],**options)
        try:
            original=subprocess.Popen
            def spawn(args,**kwargs):
                if '-m' in args and 'src.browser_worker' in args:return process
                return original(args,**kwargs)
            with patch('src.task_runner.subprocess.Popen',side_effect=spawn):
                result=run_browser_task('youtube_panel',{'channel_id':'test'},timeout=0.2)
            self.assertEqual(result['status'],'timeout')
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:process.kill();process.wait()
