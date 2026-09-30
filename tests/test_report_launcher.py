import unittest
from unittest.mock import Mock, patch
from tools import open_orchard_report as launcher

class LauncherTests(unittest.TestCase):
    @patch.object(launcher,'urlopen')
    def test_only_expected_page_is_ready(self,open_url):
        response = open_url.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = launcher.MARKER
        self.assertTrue(launcher.server_ready())
        response.read.return_value = b'<html>another application</html>'
        self.assertFalse(launcher.server_ready())

    @patch.object(launcher.subprocess,'Popen')
    @patch.object(launcher,'server_ready',return_value=True)
    def test_reuses_server(self,ready,spawn):
        self.assertEqual(launcher.ensure_server(),'existing')
        spawn.assert_not_called()

    @patch.object(launcher.subprocess,'Popen')
    @patch.object(launcher.socket,'socket')
    @patch.object(launcher,'server_ready',return_value=False)
    def test_occupied_port_is_not_replaced(self,ready,socket,spawn):
        socket.return_value.__enter__.return_value.connect_ex.return_value = 0
        with self.assertRaises(RuntimeError): launcher.ensure_server()
        spawn.assert_not_called()

if __name__ == '__main__': unittest.main()
