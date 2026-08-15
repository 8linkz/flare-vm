"""Unit tests for virtualbox/vboxcommon.py.

VBoxManage is never called for real: the subprocess layer (``__run_vboxmanage``) or the higher-level
``run_vboxmanage`` are mocked, and orchestration helpers mock the module functions they depend on.
"""

import pytest
import vboxcommon


# --------------------------------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------------------------------
class TestFormatArg:
    def test_plain_arg_is_unchanged(self):
        assert vboxcommon.format_arg("startvm") == "startvm"

    def test_arg_with_space_is_single_quoted(self):
        assert vboxcommon.format_arg("My VM") == "'My VM'"

    def test_arg_with_slash_is_quoted(self):
        assert vboxcommon.format_arg("a/b") == "'a/b'"

    def test_arg_with_backslash_is_quoted(self):
        assert vboxcommon.format_arg("a\\b") == "'a\\b'"

    def test_arg_containing_single_quote_uses_double_quotes(self):
        assert vboxcommon.format_arg("it's here") == '"it\'s here"'


def test_cmd_to_str_joins_and_quotes():
    assert vboxcommon.cmd_to_str(["VBoxManage", "startvm", "My VM"]) == "VBoxManage startvm 'My VM'"


def test_sha256_file(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"flare-vm")
    # Precomputed SHA256 of b"flare-vm".
    import hashlib

    expected = hashlib.sha256(b"flare-vm").hexdigest()
    assert vboxcommon.sha256_file(str(f)) == expected


# --------------------------------------------------------------------------------------------------
# run_vboxmanage
# --------------------------------------------------------------------------------------------------
class _Result:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


def test_run_vboxmanage_returns_stdout_on_success(monkeypatch):
    monkeypatch.setattr(vboxcommon, "__run_vboxmanage", lambda cmd, real_time=False: _Result(0, "ok output"))
    assert vboxcommon.run_vboxmanage(["list", "vms"]) == "ok output"


def test_run_vboxmanage_raises_with_parsed_error(monkeypatch):
    stdout = "VBoxManage: error: Could not find a registered machine\nsome noisy context line"
    monkeypatch.setattr(vboxcommon, "__run_vboxmanage", lambda cmd, real_time=False: _Result(1, stdout))
    with pytest.raises(RuntimeError, match="Could not find a registered machine"):
        vboxcommon.run_vboxmanage(["showvminfo", "nope"])


def test_run_vboxmanage_retries_on_verr_no_low_memory(monkeypatch):
    results = [_Result(1, "VERR_NO_LOW_MEMORY problem"), _Result(0, "recovered")]
    calls = {"n": 0}

    def fake_run(cmd, real_time=False):
        r = results[calls["n"]]
        calls["n"] += 1
        return r

    monkeypatch.setattr(vboxcommon, "__run_vboxmanage", fake_run)
    monkeypatch.setattr(vboxcommon.time, "sleep", lambda *_: None)
    assert vboxcommon.run_vboxmanage(["list", "vms"]) == "recovered"
    assert calls["n"] == 2


# --------------------------------------------------------------------------------------------------
# Output parsers (mock run_vboxmanage)
# --------------------------------------------------------------------------------------------------
def test_get_vm_uuid_found(monkeypatch):
    vms = (
        '"FLARE-VM.testing" {b76d628b-737f-40a3-9a16-c5f66ad2cfcc}\n"FLARE-VM" {a23c0c37-2062-4cf0-882b-9e9747dd33b6}\n'
    )
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: vms)
    assert vboxcommon.get_vm_uuid("FLARE-VM") == "{a23c0c37-2062-4cf0-882b-9e9747dd33b6}"


def test_get_vm_uuid_not_found(monkeypatch):
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: '"Other" {123}\n')
    assert vboxcommon.get_vm_uuid("FLARE-VM") is None


def test_get_vm_state_found(monkeypatch):
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: 'name="x"\nVMState="running"\n')
    assert vboxcommon.get_vm_state("uuid") == "running"


def test_get_vm_state_raises_when_missing(monkeypatch):
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: 'name="x"\n')
    with pytest.raises(Exception, match="Unable to get state"):
        vboxcommon.get_vm_state("uuid")


@pytest.mark.parametrize(
    "output,expected",
    [
        ("Value: 1", 1),
        ("Value: 0", 0),
        ("No value set!", 0),
        ("", 0),
    ],
)
def test_get_num_logged_in_users(monkeypatch, output, expected):
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: output)
    assert vboxcommon.get_num_logged_in_users("uuid") == expected


def test_get_hostonlyif_name_found(monkeypatch):
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: "Name:            vboxnet0\n")
    assert vboxcommon.get_hostonlyif_name() == "vboxnet0"


def test_get_hostonlyif_name_none(monkeypatch):
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: "")
    assert vboxcommon.get_hostonlyif_name() is None


# --------------------------------------------------------------------------------------------------
# wait_until
# --------------------------------------------------------------------------------------------------
def test_wait_until_returns_true_when_condition_met(monkeypatch):
    monkeypatch.setattr(vboxcommon.time, "sleep", lambda *_: None)
    monkeypatch.setattr(vboxcommon.time, "time", lambda: 0.0)
    assert vboxcommon.wait_until("uuid", "True") is True


def test_wait_until_returns_false_on_timeout(monkeypatch):
    monkeypatch.setattr(vboxcommon.time, "sleep", lambda *_: None)
    # start=0; first loop check (1s, within timeout) runs the body once with a false condition;
    # second loop check (past the 600s timeout) exits the loop and returns False.
    times = iter([0.0, 1.0, 10_000.0])
    monkeypatch.setattr(vboxcommon.time, "time", lambda: next(times))
    assert vboxcommon.wait_until("uuid", "False") is False


# --------------------------------------------------------------------------------------------------
# ensure_hostonlyif_exists
# --------------------------------------------------------------------------------------------------
def test_ensure_hostonlyif_exists_returns_existing(monkeypatch):
    monkeypatch.setattr(vboxcommon, "get_hostonlyif_name", lambda: "vboxnet0")
    assert vboxcommon.ensure_hostonlyif_exists() == "vboxnet0"


def test_ensure_hostonlyif_exists_creates_when_missing(monkeypatch):
    names = iter([None, "vboxnet1"])
    monkeypatch.setattr(vboxcommon, "get_hostonlyif_name", lambda: next(names))
    calls = []
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: calls.append(cmd))
    assert vboxcommon.ensure_hostonlyif_exists() == "vboxnet1"
    assert ["hostonlyif", "create"] in calls


def test_ensure_hostonlyif_exists_raises_if_creation_fails(monkeypatch):
    monkeypatch.setattr(vboxcommon, "get_hostonlyif_name", lambda: None)
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: None)
    with pytest.raises(RuntimeError, match="Failed to create"):
        vboxcommon.ensure_hostonlyif_exists()


# --------------------------------------------------------------------------------------------------
# ensure_vm_running / ensure_vm_shutdown
# --------------------------------------------------------------------------------------------------
def test_ensure_vm_running_starts_when_not_running(monkeypatch):
    monkeypatch.setattr(vboxcommon, "get_vm_state", lambda uuid: "poweroff")
    calls = []
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: calls.append(cmd))
    monkeypatch.setattr(vboxcommon, "wait_until", lambda uuid, cond: True)
    vboxcommon.ensure_vm_running("uuid")
    assert any(c[0] == "startvm" for c in calls)


def test_ensure_vm_running_raises_if_no_user_logs_in(monkeypatch):
    monkeypatch.setattr(vboxcommon, "get_vm_state", lambda uuid: "poweroff")
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: None)
    monkeypatch.setattr(vboxcommon, "wait_until", lambda uuid, cond: False)
    with pytest.raises(RuntimeError, match="Unable to start"):
        vboxcommon.ensure_vm_running("uuid")


def test_ensure_vm_shutdown_noop_when_poweroff(monkeypatch):
    monkeypatch.setattr(vboxcommon, "get_vm_state", lambda uuid: "poweroff")
    calls = []
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: calls.append(cmd))
    vboxcommon.ensure_vm_shutdown("uuid")
    assert calls == []


def test_ensure_vm_shutdown_returns_on_aborted(monkeypatch):
    monkeypatch.setattr(vboxcommon, "get_vm_state", lambda uuid: "aborted")
    calls = []
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: calls.append(cmd))
    vboxcommon.ensure_vm_shutdown("uuid")
    assert calls == []


def test_ensure_vm_shutdown_powers_off_running_vm(monkeypatch):
    monkeypatch.setattr(vboxcommon, "get_vm_state", lambda uuid: "running")
    calls = []
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: calls.append(cmd))
    monkeypatch.setattr(vboxcommon, "wait_until", lambda uuid, cond: True)
    vboxcommon.ensure_vm_shutdown("uuid")
    assert ["controlvm", "uuid", "poweroff"] in calls


def test_ensure_vm_shutdown_raises_if_not_powered_off(monkeypatch):
    monkeypatch.setattr(vboxcommon, "get_vm_state", lambda uuid: "running")
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: None)
    monkeypatch.setattr(vboxcommon, "wait_until", lambda uuid, cond: False)
    with pytest.raises(RuntimeError, match="Unable to shutdown"):
        vboxcommon.ensure_vm_shutdown("uuid")


# --------------------------------------------------------------------------------------------------
# snapshot helpers
# --------------------------------------------------------------------------------------------------
def test_restore_snapshot(monkeypatch):
    monkeypatch.setattr(vboxcommon, "ensure_vm_shutdown", lambda uuid: None)
    calls = []
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: calls.append(cmd))
    vboxcommon.restore_snapshot("uuid", "clean")
    assert ["snapshot", "uuid", "restore", "clean"] in calls


def test_take_snapshot_basic(monkeypatch):
    calls = []
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: calls.append(cmd))
    vboxcommon.take_snapshot("uuid", "snap1")
    assert ["snapshot", "uuid", "take", "snap1"] in calls


def test_take_snapshot_with_shutdown_and_rename(monkeypatch):
    order = []
    monkeypatch.setattr(vboxcommon, "ensure_vm_shutdown", lambda uuid: order.append("shutdown"))
    monkeypatch.setattr(vboxcommon, "rename_old_snapshot", lambda uuid, name: order.append("rename"))
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: order.append("take"))
    vboxcommon.take_snapshot("uuid", "snap1", shutdown=True, rename=True)
    assert order == ["shutdown", "rename", "take"]


def test_rename_old_snapshot_renames_each_match(monkeypatch):
    snapshots_info = 'SnapshotName="clean"\nSnapshotUUID="1"\nSnapshotName-1="clean"\nSnapshotUUID-1="2"\n'
    calls = []

    def fake(cmd, real_time=False):
        if cmd[:2] == ["snapshot", "uuid"] and "list" in cmd:
            return snapshots_info
        calls.append(cmd)

    monkeypatch.setattr(vboxcommon, "run_vboxmanage", fake)
    vboxcommon.rename_old_snapshot("uuid", "clean")
    # Two snapshots named "clean" -> two edit calls.
    assert len([c for c in calls if "edit" in c]) == 2


# --------------------------------------------------------------------------------------------------
# set_network_to_hostonly
# --------------------------------------------------------------------------------------------------
def test_set_network_to_hostonly_sets_single_hostonly(monkeypatch):
    monkeypatch.setattr(vboxcommon, "ensure_vm_shutdown", lambda uuid: None)
    monkeypatch.setattr(vboxcommon, "ensure_hostonlyif_exists", lambda: "vboxnet0")

    before = 'nic1="none"\nnic2="bridged"\nnic3="none"\n'
    after = 'nic1="hostonly"\nnic2="none"\nnic3="none"\n'
    infos = iter([before, after])
    modify_calls = []

    def fake(cmd, real_time=False):
        if cmd[0] == "showvminfo":
            return next(infos)
        modify_calls.append(cmd)

    monkeypatch.setattr(vboxcommon, "run_vboxmanage", fake)
    vboxcommon.set_network_to_hostonly("uuid")
    # nic2 (bridged) disabled, nic1 set hostonly.
    assert ["modifyvm", "uuid", "--nic2", "none"] in modify_calls
    assert ["modifyvm", "uuid", "--nic1", "hostonly"] in modify_calls


def test_set_network_to_hostonly_raises_if_not_applied(monkeypatch):
    monkeypatch.setattr(vboxcommon, "ensure_vm_shutdown", lambda uuid: None)
    monkeypatch.setattr(vboxcommon, "ensure_hostonlyif_exists", lambda: "vboxnet0")
    bad = 'nic1="bridged"\nnic2="none"\n'
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: bad)
    with pytest.raises(RuntimeError, match="Unable to change NICs"):
        vboxcommon.set_network_to_hostonly("uuid")


# --------------------------------------------------------------------------------------------------
# export_vm
# --------------------------------------------------------------------------------------------------
def test_export_vm_writes_sha256(monkeypatch, tmp_path):
    monkeypatch.setattr(vboxcommon.os.path, "expanduser", lambda p: str(tmp_path / "home"))
    monkeypatch.setattr(vboxcommon, "ensure_vm_shutdown", lambda uuid: None)

    def fake_run(cmd, real_time=False):
        # Simulate the OVA being produced by the export command.
        if cmd[0] == "export":
            output = next(a.split("=", 1)[1] for a in cmd if a.startswith("--output="))
            with open(output, "wb") as f:
                f.write(b"ova-bytes")

    monkeypatch.setattr(vboxcommon, "run_vboxmanage", fake_run)

    vboxcommon.export_vm("uuid", "FLARE-VM", description="desc", export_dir_name="EXPORTED")

    import hashlib

    ova = tmp_path / "home" / "FLARE-VM.ova"
    sha = tmp_path / "home" / "FLARE-VM.ova.sha256"
    assert ova.exists()
    assert sha.read_text() == hashlib.sha256(b"ova-bytes").hexdigest()


# --------------------------------------------------------------------------------------------------
# control_guest
# --------------------------------------------------------------------------------------------------
def test_control_guest_success(monkeypatch):
    monkeypatch.setattr(vboxcommon, "ensure_vm_running", lambda uuid: None)
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: "out")
    assert vboxcommon.control_guest("uuid", "user", "pw", ["run", "cmd.exe"]) == "out"


def test_control_guest_retries_once_on_runtime_error(monkeypatch):
    monkeypatch.setattr(vboxcommon, "ensure_vm_running", lambda uuid: None)
    monkeypatch.setattr(vboxcommon.time, "sleep", lambda *_: None)
    seq = iter([RuntimeError("guest additions not ready"), "recovered"])

    def fake(cmd, real_time=False):
        v = next(seq)
        if isinstance(v, Exception):
            raise v
        return v

    monkeypatch.setattr(vboxcommon, "run_vboxmanage", fake)
    assert vboxcommon.control_guest("uuid", "user", "pw", ["run"]) == "recovered"


# --------------------------------------------------------------------------------------------------
# __run_vboxmanage (private subprocess wrapper)
# --------------------------------------------------------------------------------------------------
def test_private_run_vboxmanage_non_frozen(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["real_time"] = "stdout" in kwargs and kwargs["stdout"] is not None
        return _Result(0, "x")

    monkeypatch.setattr(vboxcommon.subprocess, "run", fake_run)
    monkeypatch.setattr(vboxcommon.sys, "frozen", False, raising=False)
    run = getattr(vboxcommon, "__run_vboxmanage")
    assert run(["VBoxManage", "list"]).stdout == "x"
    run(["VBoxManage", "list"], real_time=True)
    assert captured["cmd"] == ["VBoxManage", "list"]


def test_private_run_vboxmanage_frozen_drops_ld_library_path(monkeypatch):
    seen_env = {}

    def fake_run(cmd, **kwargs):
        seen_env.update(kwargs.get("env", {}))
        return _Result(0, "")

    monkeypatch.setattr(vboxcommon.subprocess, "run", fake_run)
    monkeypatch.setattr(vboxcommon.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/pyinstaller/lib")
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    run = getattr(vboxcommon, "__run_vboxmanage")
    run(["VBoxManage", "list"])
    assert "LD_LIBRARY_PATH" not in seen_env


def test_private_run_vboxmanage_frozen_restores_orig_ld_library_path(monkeypatch):
    seen_env = {}

    def fake_run(cmd, **kwargs):
        seen_env.update(kwargs.get("env", {}))
        return _Result(0, "")

    monkeypatch.setattr(vboxcommon.subprocess, "run", fake_run)
    monkeypatch.setattr(vboxcommon.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/pyinstaller/lib")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/system/lib")
    run = getattr(vboxcommon, "__run_vboxmanage")
    run(["VBoxManage", "list"])
    assert seen_env.get("LD_LIBRARY_PATH") == "/system/lib"


# --------------------------------------------------------------------------------------------------
# extra branches
# --------------------------------------------------------------------------------------------------
def test_ensure_vm_shutdown_handles_saved_state(monkeypatch):
    states = iter(["saved", "running"])
    monkeypatch.setattr(vboxcommon, "get_vm_state", lambda uuid: next(states))
    monkeypatch.setattr(vboxcommon, "ensure_vm_running", lambda uuid: None)
    monkeypatch.setattr(vboxcommon, "wait_until", lambda uuid, cond: True)
    calls = []
    monkeypatch.setattr(vboxcommon, "run_vboxmanage", lambda cmd, real_time=False: calls.append(cmd))
    vboxcommon.ensure_vm_shutdown("uuid")
    assert ["controlvm", "uuid", "poweroff"] in calls


def test_export_vm_renames_pre_existing_ova(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "FLARE-VM.ova").write_bytes(b"old ova")
    monkeypatch.setattr(vboxcommon.os.path, "expanduser", lambda p: str(home))
    monkeypatch.setattr(vboxcommon, "ensure_vm_shutdown", lambda uuid: None)

    def fake_run(cmd, real_time=False):
        if cmd[0] == "export":
            output = next(a.split("=", 1)[1] for a in cmd if a.startswith("--output="))
            with open(output, "wb") as f:
                f.write(b"new ova")

    monkeypatch.setattr(vboxcommon, "run_vboxmanage", fake_run)
    vboxcommon.export_vm("uuid", "FLARE-VM", export_dir_name="EXPORTED")

    renamed = [
        p.name
        for p in home.iterdir()
        if p.name.startswith("FLARE-VM.") and p.name.endswith(".ova") and p.name != "FLARE-VM.ova"
    ]
    assert renamed, "expected the old OVA to be renamed with a timestamp"
