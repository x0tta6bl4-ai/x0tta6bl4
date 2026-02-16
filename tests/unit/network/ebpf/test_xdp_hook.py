from pathlib import Path
from unittest.mock import Mock, patch

from src.network.ebpf.hooks.xdp_hook import XDPHook


def test_xdp_hook_attach_detach_cycle(tmp_path):
    hook = XDPHook()

    # Create dummy program file
    program_file = tmp_path / "xdp_prog.o"
    program_file.write_bytes(b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48)
    other_file = tmp_path / "xdp_other.o"
    other_file.write_bytes(b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48)

    # Mock interface check and subprocess calls
    def mock_path_exists(self):
        path_str = str(self)
        if "eth0" in path_str or "xdp_prog" in path_str or "xdp_other" in path_str:
            return True
        return False

    # Mock subprocess.run to return success with xdp in stdout for verification
    def mock_subprocess_run(cmd, **kwargs):
        # For ip link show - return stdout with xdp
        if "show" in cmd:
            return Mock(returncode=0, stdout="xdp", stderr="")
        # For ip link set - return success
        return Mock(returncode=0, stdout="", stderr="")

    with (
        patch.object(Path, "exists", mock_path_exists),
        patch.object(Path, "read_text", return_value="up"),
        patch("subprocess.run", side_effect=mock_subprocess_run),
    ):

        assert hook.attach("eth0", str(program_file), mode="native") is True
        # second attach should warn and return False
        assert hook.attach("eth0", str(other_file), mode="generic") is False
        info = hook.get_attached_program("eth0")
        assert info["program"] == str(program_file)
        assert info["mode"] == "native"
        assert "eth0" in hook.list_attached_interfaces()

        # Mock detach - ip link show should not contain xdp after detach
        def mock_subprocess_run_detach(cmd, **kwargs):
            if "show" in cmd:
                return Mock(returncode=0, stdout="", stderr="")  # No xdp in stdout
            return Mock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=mock_subprocess_run_detach):
            assert hook.detach("eth0") is True
            assert hook.get_attached_program("eth0") is None
            assert hook.detach("eth0") is False  # already detached
