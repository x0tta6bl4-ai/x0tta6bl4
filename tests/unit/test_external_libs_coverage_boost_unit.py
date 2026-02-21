"""Coverage-oriented sanity tests for third-party libs loaded in our suite."""

from __future__ import annotations

import codecs
import itertools
import io
import types

import chardet
import markupsafe
import pytest
from chardet.big5prober import Big5Prober
from chardet.cp949prober import CP949Prober
from chardet.eucjpprober import EUCJPProber
from chardet.euckrprober import EUCKRProber
from chardet.euctwprober import EUCTWProber
from chardet.gb2312prober import GB2312Prober
from chardet.johabprober import JOHABProber
from chardet.mbcsgroupprober import MBCSGroupProber
from chardet.sbcsgroupprober import SBCSGroupProber
from chardet.sjisprober import SJISProber
from chardet.universaldetector import UniversalDetector
from chardet.utf8prober import UTF8Prober
from colorama import ansi as color_ansi
from colorama import ansitowin32, initialise, winterm
from markupsafe import Markup
from packaging import _manylinux, markers, requirements, specifiers, tags, utils as pkg_utils, version


def test_packaging_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    left = tags.Tag("CP312", "ABI3", "manylinux_2_17_x86_64")
    right = tags.Tag("cp312", "abi3", "manylinux_2_17_x86_64")

    assert left.interpreter == "cp312"
    assert left.abi == "abi3"
    assert left.platform == "manylinux_2_17_x86_64"
    assert left == right
    assert left != object()
    assert hash(left) == hash(right)
    assert str(left) == "cp312-abi3-manylinux_2_17_x86_64"
    assert "cp312-abi3-manylinux_2_17_x86_64" in repr(left)

    parsed = tags.parse_tag("py3.py2-none-any.manylinux1_x86_64")
    assert len(parsed) >= 2

    monkeypatch.setattr(tags.sysconfig, "get_config_var", lambda _name: None)
    assert tags._get_config_var("DEFINITELY_MISSING", warn=True) is None
    assert tags._normalize_string("a.b-c d") == "a_b_c_d"
    assert tags._is_threaded_cpython([]) is False
    assert tags._is_threaded_cpython(["cp313t"]) is True
    assert tags._abi3_applies((3, 12), False) is True
    assert tags._abi3_applies((3, 1), False) is False

    cp_abis = tags._cpython_abis((3, 12), warn=True)
    assert cp_abis and cp_abis[0].startswith("cp")
    cpython = list(
        itertools.islice(
            tags.cpython_tags(
                (3, 12), abis=cp_abis[:1], platforms=["manylinux_2_17_x86_64"]
            ),
            8,
        )
    )
    assert cpython
    assert list(itertools.islice(tags.generic_tags("py3", ["abi3"], ["any"]), 3))
    assert list(itertools.islice(tags.compatible_tags((3, 12), "py3", ["any"]), 3))

    assert version.Version("1.2.3") < version.Version("2.0")
    assert version.parse("1.0") == version.Version("1.0")
    with pytest.raises(version.InvalidVersion):
        version.Version("1..0")

    s = specifiers.SpecifierSet(">=1.0,!=1.3.*,<2.0")
    assert "1.2" in s
    assert "1.3.5" not in s
    assert "2.0" not in s
    assert "1.9" in list(s.filter(["0.9", "1.2", "1.3.1", "1.9", "2.0"]))
    with pytest.raises(specifiers.InvalidSpecifier):
        specifiers.Specifier("=>1.0")

    req = requirements.Requirement("demo-pkg[fast]>=1.0; python_version >= '3.8'")
    assert req.name == "demo-pkg"
    assert req.marker is not None and req.marker.evaluate()
    with pytest.raises(requirements.InvalidRequirement):
        requirements.Requirement("not a valid requirement ???")

    m = markers.Marker("os_name == 'posix' or os_name == 'nt'")
    assert m.evaluate() is True
    with pytest.raises(markers.InvalidMarker):
        markers.Marker("python_version >< '3.8'")


def test_chardet_paths() -> None:
    detector = UniversalDetector(should_rename_legacy=True)
    detector.feed(codecs.BOM_UTF8 + "hello".encode("utf-8"))
    result = detector.close()
    assert result["encoding"] in {"UTF-8-SIG", "UTF-8"}

    detector = UniversalDetector()
    for chunk in [
        b"simple ascii text",
        "Привет мир".encode("cp1251"),
        "こんにちは世界".encode("utf-8"),
        bytes(range(32, 128)) * 3,
    ]:
        detector.feed(chunk)
    result = detector.close()
    assert "encoding" in result

    for payload in [
        b"plain-ascii",
        "naive caf\xe9".encode("latin-1"),
        "данные".encode("koi8-r"),
    ]:
        detected = chardet.detect(payload)
        assert "encoding" in detected
        assert "confidence" in detected

    mb_group = MBCSGroupProber()
    mb_group.feed(bytearray(b"\x81\x40\x81\x41hello"))
    _ = mb_group.get_confidence()
    _ = mb_group.charset_name
    _ = mb_group.language

    sb_group = SBCSGroupProber()
    sb_group.feed(bytearray(b"english text with punctuation!"))
    _ = sb_group.get_confidence()
    _ = sb_group.charset_name
    _ = sb_group.language

    for prober_cls in (
        UTF8Prober,
        SJISProber,
        EUCJPProber,
        GB2312Prober,
        EUCKRProber,
        CP949Prober,
        Big5Prober,
        EUCTWProber,
        JOHABProber,
    ):
        prober = prober_cls()
        prober.feed(bytearray(b"\x81\x40abc"))
        _ = prober.get_confidence()
        _ = prober.charset_name
        _ = prober.language


def test_packaging_tags_additional_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    assert tags._is_threaded_cpython(["not-a-cpython-abi"]) is False

    monkeypatch.setattr(tags, "EXTENSION_SUFFIXES", [".cpython-312-d.so"])
    monkeypatch.setattr(tags, "_get_config_var", lambda _name, warn=False: None)
    debug_abis = tags._cpython_abis((3, 12), warn=True)
    assert debug_abis and debug_abis[0].startswith("cp312")

    monkeypatch.setattr(tags, "_get_config_var", lambda _name, warn=False: ".pyd")
    assert tags._generic_abi()

    monkeypatch.setattr(tags, "_get_config_var", lambda _name, warn=False: ".graalpy-38-native-x86_64-darwin.dylib")
    assert tags._generic_abi()

    monkeypatch.setattr(tags, "_get_config_var", lambda _name, warn=False: "invalid")
    with pytest.raises(SystemError):
        tags._generic_abi()

    monkeypatch.setattr(
        tags, "_get_config_var", lambda _name, warn=False: ".cpython-312-x86_64-linux-gnu.so"
    )
    assert list(itertools.islice(tags.cpython_tags(), 4))
    assert list(itertools.islice(tags.cpython_tags((3,), abis=["abi3", "none"], platforms=["any"]), 3))
    assert list(itertools.islice(tags.generic_tags(), 3))
    assert list(tags._py_interpreter_range((3, 11)))
    assert list(itertools.islice(tags.compatible_tags((3, 11), interpreter="py3", platforms=["any"]), 6))


def test_colorama_ansi_and_initialise_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    assert color_ansi.set_title("demo")
    assert color_ansi.clear_screen(1)
    assert color_ansi.clear_line(0)
    assert color_ansi.Cursor.UP(2)
    assert color_ansi.Cursor.DOWN(2)
    assert color_ansi.Cursor.FORWARD(2)
    assert color_ansi.Cursor.BACK(2)
    assert color_ansi.Cursor.POS(3, 4)

    initialise._wipe_internal_state_for_tests()
    with pytest.raises(ValueError):
        initialise.init(autoreset=True, wrap=False)

    with initialise.colorama_text(autoreset=False, convert=False, strip=False):
        pass
    initialise.reinit()
    initialise.deinit()

    monkeypatch.setattr(initialise.sys, "platform", "win32")
    initialise._wipe_internal_state_for_tests()

    class _FakeAnsiWrapper:
        def __init__(self, stream, convert=None, strip=None, autoreset=False):
            self.stream = stream
            self.convert = stream is initialise.sys.stdout

    monkeypatch.setattr(initialise, "AnsiToWin32", _FakeAnsiWrapper)
    initialise.just_fix_windows_console()
    assert initialise.fixed_windows_console is True


def test_colorama_ansitowin32_and_winterm_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Wrapped:
        def __init__(self):
            self.buffer = []
            self.closed = False

        def write(self, text):
            self.buffer.append(text)

        def flush(self):
            return None

        def isatty(self):
            return True

        def fileno(self):
            return 1

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Converter:
        def __init__(self):
            self.data = []

        def write(self, text):
            self.data.append(text)

    wrapped = _Wrapped()
    converter = _Converter()
    proxy = ansitowin32.StreamWrapper(wrapped, converter)
    assert proxy.__enter__() is wrapped
    assert proxy.__exit__(None, None, None) is False
    proxy.write("x")
    assert converter.data == ["x"]
    assert proxy.isatty() is True
    assert proxy.closed is False

    writer = ansitowin32.AnsiToWin32(wrapped, convert=False, strip=True, autoreset=True)
    writer.write("\x1b[31mhello\x1b[0m")
    writer.reset_all()

    class _Coord:
        def __init__(self, x, y):
            self.X = x
            self.Y = y

    class _Info:
        def __init__(self):
            self.wAttributes = 7
            self.dwCursorPosition = _Coord(1, 1)
            self.dwSize = _Coord(80, 25)

    class _FakeWin32:
        STDOUT = 1
        STDERR = 2
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 4
        windll = object()

        def __init__(self):
            self._mode = 0

        def winapi_test(self):
            return True

        def GetConsoleScreenBufferInfo(self, _handle):
            return _Info()

        def SetConsoleTextAttribute(self, _handle, _attrs):
            return None

        def SetConsoleCursorPosition(self, _handle, _position, adjust=True):
            return None

        def FillConsoleOutputCharacter(self, _handle, _char, _cells, _coord):
            return None

        def FillConsoleOutputAttribute(self, _handle, _attrs, _cells, _coord):
            return None

        def SetConsoleTitle(self, _title):
            return None

        def COORD(self, x, y):
            return _Coord(x, y)

        def GetConsoleMode(self, _handle):
            return self._mode

        def SetConsoleMode(self, _handle, mode):
            self._mode = mode
            return None

    fake_win32 = _FakeWin32()
    monkeypatch.setattr(winterm, "win32", fake_win32)
    monkeypatch.setattr(winterm, "get_osfhandle", lambda fd: fd)

    term = winterm.WinTerm()
    term.get_attrs()
    term.set_attrs(7)
    term.reset_all()
    term.fore()
    term.back()
    term.style()
    term.set_console()
    term.get_position(fake_win32.STDOUT)
    term.set_cursor_position((1, 1))
    term.set_cursor_position(None)
    term.cursor_adjust(1, 1)
    term.erase_screen(0)
    term.erase_screen(1)
    term.erase_screen(2)
    term.erase_screen(99)
    term.erase_line(0)
    term.erase_line(1)
    term.erase_line(2)
    term.erase_line(99)
    term.set_title("demo")

    assert winterm.enable_vt_processing(1) is True
    monkeypatch.setattr(winterm, "get_osfhandle", lambda _fd: (_ for _ in ()).throw(TypeError("boom")))
    assert winterm.enable_vt_processing(1) is False


def test_markupsafe_paths() -> None:
    class _Html:
        def __html__(self) -> str:
            return "<b>x</b>"

    class _HtmlMarkup:
        def __html__(self) -> Markup:
            return Markup("<i>x</i>")

    class _HtmlFormatter:
        def __html_format__(self, format_spec: str) -> str:
            return f"<{format_spec}>"

    class _SubMarkup(Markup):
        pass

    base = Markup(_Html())
    assert base.__html__() is base
    assert base + "<x>" == Markup("<b>x</b>&lt;x&gt;")
    assert "<x>" + base == Markup("&lt;x&gt;<b>x</b>")
    assert base * 2 == Markup("<b>x</b><b>x</b>")
    assert Markup.__add__(base, object()) is NotImplemented
    assert Markup.__radd__(base, object()) is NotImplemented
    assert Markup.__mul__(base, "bad") is NotImplemented

    assert Markup("<em>%s</em>") % ("foo & bar",) == Markup("<em>foo &amp; bar</em>")
    assert Markup("%(name)s") % {"name": "<tag>"} == Markup("&lt;tag&gt;")
    assert Markup("%d %.1f %r") % (3, 2.5, "<x>") == Markup("3 2.5 &#39;&lt;x&gt;&#39;")

    joined = Markup(",").join(["a", "<b>", _Html()])
    assert joined == Markup("a,&lt;b&gt;,<b>x</b>")
    assert all(isinstance(item, Markup) for item in Markup("a,b").split(","))
    assert all(isinstance(item, Markup) for item in Markup("a,b").rsplit(",", 1))
    assert all(isinstance(item, Markup) for item in Markup("a\nb").splitlines())

    assert Markup("Main &raquo; <em>About</em>").unescape() == "Main » <em>About</em>"
    assert Markup("Main <!--hidden--> <em>About</em>").striptags() == "Main About"
    assert Markup("Main <!--broken").striptags() == "Main <!--broken"
    assert Markup("text <broken").striptags() == "text <broken"

    left, sep, right = Markup("abca").partition("b")
    assert (left, sep, right) == (Markup("a"), Markup("b"), Markup("ca"))
    left, sep, right = Markup("abca").rpartition("b")
    assert (left, sep, right) == (Markup("a"), Markup("b"), Markup("ca"))

    assert Markup("safe").__html_format__("") == Markup("safe")
    with pytest.raises(ValueError):
        Markup("safe").__html_format__("x")

    assert Markup("{x}").format_map({"x": "<tag>"}) == Markup("&lt;tag&gt;")
    assert Markup("{0:tag}").format(_HtmlFormatter()) == Markup("&lt;tag&gt;")
    assert Markup("{}").format(_HtmlMarkup()) == Markup("<i>x</i>")
    with pytest.raises(ValueError):
        Markup("{:>4}").format(_Html())

    assert isinstance(Markup.escape("<x>"), Markup)
    assert isinstance(_SubMarkup.escape("<x>"), _SubMarkup)
    assert Markup("ABC").lower() == Markup("abc")
    assert Markup("xy").center(4, "0") == Markup("0xy0")

    escaped = markupsafe._escape_argspec({"k": "<v>", "n": 1}, [("k", "<v>"), ("n", 1)], Markup.escape)
    assert escaped["k"] == Markup("&lt;v&gt;")
    helper = markupsafe._MarkupEscapeHelper({"k": "<x>"}, Markup.escape)
    assert str(helper["k"]) == "&lt;x&gt;"
    assert str(markupsafe._MarkupEscapeHelper("<x>", Markup.escape)) == "&lt;x&gt;"
    assert repr(markupsafe._MarkupEscapeHelper("<x>", Markup.escape)) == "&#39;&lt;x&gt;&#39;"
    assert int(markupsafe._MarkupEscapeHelper("7", Markup.escape)) == 7
    assert float(markupsafe._MarkupEscapeHelper("3.5", Markup.escape)) == 3.5


def test_packaging_specifiers_additional_branches() -> None:
    spec = specifiers.Specifier("==1.2a1")
    assert spec.prereleases is True
    spec = specifiers.Specifier(">=1")
    assert spec.prereleases is False
    spec.prereleases = True
    assert spec.prereleases is True
    assert "prereleases=True" in repr(spec)
    assert spec == ">=1.0"
    assert spec.__eq__("definitely-not-a-specifier") is NotImplemented
    assert spec.__eq__(object()) is NotImplemented
    assert hash(spec)
    assert spec._canonical_spec[0] == ">="

    assert specifiers.Specifier("<3.1").contains("3.1.dev0") is False
    assert specifiers.Specifier(">3.1").contains("3.1.post1") is False
    assert specifiers.Specifier(">3.1").contains("3.1+local") is False
    assert specifiers.Specifier("===1.0+ABC").contains("1.0+abc") is True
    assert list(specifiers.Specifier(">=1.2.3").filter(["1.2", "1.5a1"])) == ["1.5a1"]

    assert specifiers._version_split("1!2.3rc1") == ["1", "2", "3", "rc1"]
    assert specifiers._version_join(["1", "2", "3"]) == "1!2.3"
    assert specifiers._is_not_suffix("rc1") is False
    assert specifiers._is_not_suffix("9") is True
    assert specifiers._pad_version(["1", "2"], ["1", "2", "3"]) == (
        ["1", "2", "0"],
        ["1", "2", "3"],
    )

    empty = specifiers.SpecifierSet("")
    assert empty.prereleases is None
    assert list(empty.filter(["1.3", "1.5a1"])) == ["1.3"]
    assert list(empty.filter(["1.5a1"])) == ["1.5a1"]
    assert list(empty.filter(["1.3", "1.5a1"], prereleases=True)) == ["1.3", "1.5a1"]

    left = specifiers.SpecifierSet(">=1", prereleases=True)
    right = specifiers.SpecifierSet("<=2", prereleases=False)
    with pytest.raises(ValueError):
        _ = left & right

    combined = specifiers.SpecifierSet(">=1") & "<=2"
    assert combined.contains("1.5")
    assert specifiers.SpecifierSet(">=1").__and__(1) is NotImplemented

    base = specifiers.SpecifierSet(">=1,!=1.1")
    assert len(base) == 2
    assert sorted(str(item) for item in base) == ["!=1.1", ">=1"]
    assert "1.2" in base
    assert base.__eq__(specifiers.Specifier(">=1")) is False
    assert specifiers.SpecifierSet(">=1").__eq__(specifiers.Specifier(">=1")) is True
    assert specifiers.SpecifierSet(">=1").__eq__(object()) is NotImplemented
    assert (
        specifiers.SpecifierSet(">=1").contains(
            "1.0a1", installed=True, prereleases=True
        )
        is False
    )
    assert list(specifiers.SpecifierSet(">=1,<=2").filter(["0.9", "1.5", "2.1"])) == ["1.5"]


def test_packaging_tags_platform_and_sys_tags_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    assert tags._mac_arch("x86_64", is_32bit=False) == "x86_64"
    assert tags._mac_arch("ppc64", is_32bit=True) == "ppc"
    assert tags._mac_arch("arm64", is_32bit=True) == "i386"
    assert tags._mac_binary_formats((10, 3), "x86_64") == []
    assert tags._mac_binary_formats((10, 7), "ppc") == []
    assert tags._mac_binary_formats((10, 6), "ppc64") == []
    assert "universal2" in tags._mac_binary_formats((11, 0), "arm64")

    monkeypatch.setattr(tags.platform, "mac_ver", lambda: ("10.16.0", ("", "", ""), "x86_64"))
    monkeypatch.setattr(
        tags.subprocess,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(stdout="11.2.1\n"),
    )
    assert list(itertools.islice(tags.mac_platforms(), 8))
    assert any("universal2" in value for value in tags.mac_platforms((11, 1), "arm64"))
    assert any("macosx_10_16" in value for value in tags.mac_platforms((11, 1), "x86_64"))

    monkeypatch.setattr(tags.sysconfig, "get_platform", lambda: "custom-platform")
    assert list(tags._linux_platforms()) == ["custom_platform"]
    monkeypatch.setattr(tags._manylinux, "platform_tags", lambda archs: [f"many_{arch}" for arch in archs])
    monkeypatch.setattr(tags._musllinux, "platform_tags", lambda archs: [f"musl_{arch}" for arch in archs])
    monkeypatch.setattr(tags.sysconfig, "get_platform", lambda: "linux_x86_64")
    assert list(tags._linux_platforms(is_32bit=True)) == ["many_i686", "musl_i686", "linux_i686"]
    monkeypatch.setattr(tags.sysconfig, "get_platform", lambda: "linux_aarch64")
    linux_arm = list(tags._linux_platforms(is_32bit=True))
    assert "linux_armv8l" in linux_arm
    assert "linux_armv7l" in linux_arm

    monkeypatch.setattr(tags.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(tags, "mac_platforms", lambda *args, **kwargs: iter(["mac_tag"]))
    assert list(tags.platform_tags()) == ["mac_tag"]
    monkeypatch.setattr(tags.platform, "system", lambda: "Linux")
    monkeypatch.setattr(tags, "_linux_platforms", lambda *args, **kwargs: iter(["linux_tag"]))
    assert list(tags.platform_tags()) == ["linux_tag"]
    monkeypatch.setattr(tags.platform, "system", lambda: "Other")
    monkeypatch.setattr(tags, "_generic_platforms", lambda: iter(["generic_tag"]))
    assert list(tags.platform_tags()) == ["generic_tag"]

    monkeypatch.setattr(tags.sys, "implementation", types.SimpleNamespace(name="cpython"))
    assert tags.interpreter_name() == "cp"
    monkeypatch.setattr(tags.sys, "implementation", types.SimpleNamespace(name="custom"))
    assert tags.interpreter_name() == "custom"
    monkeypatch.setattr(tags, "_get_config_var", lambda _name, warn=False: None)
    monkeypatch.setattr(tags.sys, "version_info", (3, 12, 5))
    assert tags.interpreter_version(warn=True) == "312"
    monkeypatch.setattr(tags, "_get_config_var", lambda _name, warn=False: "313")
    assert tags.interpreter_version() == "313"

    captured = []
    monkeypatch.setattr(tags, "interpreter_name", lambda: "cp")
    monkeypatch.setattr(tags, "cpython_tags", lambda **kwargs: iter([tags.Tag("cp312", "abi3", "any")]))
    monkeypatch.setattr(
        tags,
        "compatible_tags",
        lambda **kwargs: (captured.append(kwargs.get("interpreter")) or iter([tags.Tag("py3", "none", "any")])),
    )
    assert len(list(tags.sys_tags(warn=True))) == 2
    assert captured[-1] == "cp313"

    monkeypatch.setattr(tags, "interpreter_name", lambda: "pp")
    monkeypatch.setattr(tags, "generic_tags", lambda **kwargs: iter([tags.Tag("pp38", "none", "any")]))
    assert len(list(tags.sys_tags())) == 2
    assert captured[-1] == "pp3"


def test_packaging_utils_paths() -> None:
    assert pkg_utils.canonicalize_name("My_Pkg.Name") == "my-pkg-name"
    assert pkg_utils.canonicalize_name("valid-name", validate=True) == "valid-name"
    with pytest.raises(pkg_utils.InvalidName):
        pkg_utils.canonicalize_name("-bad-", validate=True)

    assert pkg_utils.is_normalized_name("demo-pkg") is True
    assert pkg_utils.is_normalized_name("Demo_Pkg") is False

    assert pkg_utils.canonicalize_version("1!2.0.0.post1.dev2+LOCAL") == "1!2.post1.dev2+local"
    assert pkg_utils.canonicalize_version("definitely-invalid-version") == "definitely-invalid-version"

    name, parsed_version, build, wheel_tags = pkg_utils.parse_wheel_filename(
        "demo_pkg-1.2.3-1abc-py3-none-any.whl"
    )
    assert name == "demo-pkg"
    assert str(parsed_version) == "1.2.3"
    assert build == (1, "abc")
    assert wheel_tags

    name, parsed_version, build, wheel_tags = pkg_utils.parse_wheel_filename(
        "demo_pkg-1.2.3-py3-none-any.whl"
    )
    assert name == "demo-pkg"
    assert str(parsed_version) == "1.2.3"
    assert build == ()
    assert wheel_tags

    with pytest.raises(pkg_utils.InvalidWheelFilename):
        pkg_utils.parse_wheel_filename("demo.whl.txt")
    with pytest.raises(pkg_utils.InvalidWheelFilename):
        pkg_utils.parse_wheel_filename("too-few-parts.whl")
    with pytest.raises(pkg_utils.InvalidWheelFilename):
        pkg_utils.parse_wheel_filename("bad__name-1.2.3-py3-none-any.whl")
    with pytest.raises(pkg_utils.InvalidWheelFilename):
        pkg_utils.parse_wheel_filename("demo-1..2-py3-none-any.whl")
    with pytest.raises(pkg_utils.InvalidWheelFilename):
        pkg_utils.parse_wheel_filename("demo-1.2.3-abc-py3-none-any.whl")

    sdist_name, sdist_version = pkg_utils.parse_sdist_filename("demo_pkg-1.0.0.tar.gz")
    assert sdist_name == "demo-pkg"
    assert str(sdist_version) == "1.0.0"
    sdist_name, sdist_version = pkg_utils.parse_sdist_filename("demo_pkg-1.0.0.zip")
    assert sdist_name == "demo-pkg"
    assert str(sdist_version) == "1.0.0"

    with pytest.raises(pkg_utils.InvalidSdistFilename):
        pkg_utils.parse_sdist_filename("demo_pkg-1.0.0.tgz")
    with pytest.raises(pkg_utils.InvalidSdistFilename):
        pkg_utils.parse_sdist_filename("demo_pkg.tar.gz")
    with pytest.raises(pkg_utils.InvalidSdistFilename):
        pkg_utils.parse_sdist_filename("demo_pkg-not.a.version.tar.gz")


def test_packaging_manylinux_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    with _manylinux._parse_elf(None) as parsed:
        assert parsed is None

    monkeypatch.setattr(_manylinux, "_is_linux_armhf", lambda _exe: True)
    monkeypatch.setattr(_manylinux, "_is_linux_i686", lambda _exe: False)
    assert _manylinux._have_compatible_abi("python", ["armv7l"]) is True
    assert _manylinux._have_compatible_abi("python", ["i686"]) is False
    assert _manylinux._have_compatible_abi("python", ["x86_64"]) is True
    assert _manylinux._have_compatible_abi("python", ["definitely_unknown"]) is False

    monkeypatch.setattr(_manylinux.os, "confstr", lambda _key: "glibc 2.31")
    assert _manylinux._glibc_version_string_confstr() == "2.31"
    monkeypatch.setattr(
        _manylinux.os,
        "confstr",
        lambda _key: (_ for _ in ()).throw(OSError("confstr unavailable")),
    )
    assert _manylinux._glibc_version_string_confstr() is None

    with pytest.warns(RuntimeWarning):
        assert _manylinux._parse_glibc_version("invalid") == (-1, -1)

    _manylinux._get_glibc_version.cache_clear()
    monkeypatch.setattr(_manylinux, "_glibc_version_string", lambda: "2.28")
    assert _manylinux._get_glibc_version() == (2, 28)
    _manylinux._get_glibc_version.cache_clear()
    monkeypatch.setattr(_manylinux, "_glibc_version_string", lambda: None)
    assert _manylinux._get_glibc_version() == (-1, -1)

    monkeypatch.setattr(_manylinux, "_get_glibc_version", lambda: (2, 17))
    assert _manylinux._is_compatible("x86_64", _manylinux._GLibCVersion(2, 18)) is False

    import builtins
    import sys

    real_import = builtins.__import__

    def _import_without_manylinux(name, *args, **kwargs):
        if name == "_manylinux":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import_without_manylinux)
    assert _manylinux._is_compatible("x86_64", _manylinux._GLibCVersion(2, 17)) is True
    monkeypatch.setattr(builtins, "__import__", real_import)

    monkeypatch.setitem(
        sys.modules,
        "_manylinux",
        types.SimpleNamespace(manylinux_compatible=lambda *_args: False),
    )
    assert _manylinux._is_compatible("x86_64", _manylinux._GLibCVersion(2, 17)) is False
    monkeypatch.setitem(
        sys.modules,
        "_manylinux",
        types.SimpleNamespace(manylinux_compatible=lambda *_args: None),
    )
    assert _manylinux._is_compatible("x86_64", _manylinux._GLibCVersion(2, 17)) is True
    monkeypatch.setitem(sys.modules, "_manylinux", types.SimpleNamespace(manylinux1_compatible=False))
    assert _manylinux._is_compatible("x86_64", _manylinux._GLibCVersion(2, 5)) is False
    monkeypatch.setitem(
        sys.modules,
        "_manylinux",
        types.SimpleNamespace(manylinux2010_compatible=True),
    )
    assert _manylinux._is_compatible("x86_64", _manylinux._GLibCVersion(2, 12)) is True
    monkeypatch.setitem(
        sys.modules,
        "_manylinux",
        types.SimpleNamespace(manylinux2014_compatible=False),
    )
    assert _manylinux._is_compatible("x86_64", _manylinux._GLibCVersion(2, 17)) is False

    monkeypatch.setattr(_manylinux, "_have_compatible_abi", lambda _exe, _archs: False)
    assert list(_manylinux.platform_tags(["x86_64"])) == []

    monkeypatch.setattr(_manylinux, "_have_compatible_abi", lambda _exe, _archs: True)
    monkeypatch.setattr(_manylinux, "_get_glibc_version", lambda: (2, 17))
    monkeypatch.setattr(
        _manylinux,
        "_is_compatible",
        lambda _arch, glibc_version: glibc_version.minor >= 16,
    )
    generated = list(itertools.islice(_manylinux.platform_tags(["x86_64"]), 8))
    assert generated
    assert any(tag.startswith("manylinux_2_17_x86_64") for tag in generated)


def test_colorama_ansitowin32_convert_and_osc_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Wrapped:
        def __init__(self):
            self.buf = []
            self.closed = False

        def write(self, text):
            self.buf.append(text)

        def flush(self):
            return None

        def isatty(self):
            return True

        def fileno(self):
            return 1

    class _FakeWinterm:
        def __init__(self):
            self.calls = []

        def reset_all(self, **kwargs):
            self.calls.append(("reset", kwargs))

        def style(self, *args, **kwargs):
            self.calls.append(("style", args, kwargs))

        def fore(self, *args, **kwargs):
            self.calls.append(("fore", args, kwargs))

        def back(self, *args, **kwargs):
            self.calls.append(("back", args, kwargs))

        def erase_screen(self, *args, **kwargs):
            self.calls.append(("erase_screen", args, kwargs))

        def erase_line(self, *args, **kwargs):
            self.calls.append(("erase_line", args, kwargs))

        def set_cursor_position(self, *args, **kwargs):
            self.calls.append(("set_cursor_position", args, kwargs))

        def cursor_adjust(self, *args, **kwargs):
            self.calls.append(("cursor_adjust", args, kwargs))

        def set_title(self, *args, **kwargs):
            self.calls.append(("set_title", args, kwargs))

    wrapped = _Wrapped()
    fake_term = _FakeWinterm()
    monkeypatch.setattr(ansitowin32.os, "name", "nt")
    monkeypatch.setattr(ansitowin32, "winapi_test", lambda: True)
    monkeypatch.setattr(ansitowin32, "enable_vt_processing", lambda _fd: False)
    monkeypatch.setattr(ansitowin32, "winterm", fake_term)

    writer = ansitowin32.AnsiToWin32(wrapped, convert=None, strip=None, autoreset=False)
    assert writer.should_wrap() is True
    assert writer.convert is True
    assert writer.strip is True
    writer.write("\x1b[31mRED\x1b[0m")
    assert wrapped.buf == ["RED"]

    assert writer.extract_params("H", "") == (1, 1)
    assert writer.extract_params("J", "") == (0,)
    assert writer.extract_params("A", "") == (1,)
    writer.call_win32("J", (2,))
    writer.call_win32("K", (1,))
    writer.call_win32("H", (3, 4))
    writer.call_win32("A", (2,))
    writer.call_win32("B", (2,))
    writer.call_win32("C", (2,))
    writer.call_win32("D", (2,))
    assert writer.convert_osc("\x1b]2;TITLE\a") == ""
    assert any(call[0] == "set_title" for call in fake_term.calls)
