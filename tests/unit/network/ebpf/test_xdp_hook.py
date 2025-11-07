from src.network.ebpf.hooks.xdp_hook import XDPHook


def test_xdp_hook_attach_detach_cycle():
    hook = XDPHook()
    assert hook.attach('eth0', 'xdp_prog.o', mode='native') is True
    # second attach should warn and return False
    assert hook.attach('eth0', 'xdp_other.o', mode='generic') is False
    info = hook.get_attached_program('eth0')
    assert info['program'] == 'xdp_prog.o'
    assert info['mode'] == 'native'
    assert 'eth0' in hook.list_attached_interfaces()
    assert hook.detach('eth0') is True
    assert hook.get_attached_program('eth0') is None
    assert hook.detach('eth0') is False  # already detached
