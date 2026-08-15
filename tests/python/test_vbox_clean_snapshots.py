"""Unit tests for virtualbox/vbox-clean-snapshots.py (snapshot-tree logic).

The module is loaded via the ``clean_snapshots`` fixture (importlib, since the filename has dashes).
It imports ``run_vboxmanage``/``get_vm_state`` from vboxcommon with ``from ... import``, so those names
are patched on the module object itself. VBoxManage is never called for real.
"""

SNAPSHOTS_INFO = (
    'SnapshotName="ROOT"\n'
    'SnapshotUUID="uuid-root"\n'
    'SnapshotName-1="Snapshot 1"\n'
    'SnapshotUUID-1="uuid-1"\n'
    'SnapshotName-1-1="Snapshot 2"\n'
    'SnapshotUUID-1-1="uuid-1-1"\n'
    'SnapshotName-2="Snapshot 3"\n'
    'SnapshotUUID-2="uuid-2"\n'
)


class TestIsProtected:
    def test_matches_substring_case_insensitively(self, clean_snapshots):
        assert clean_snapshots.is_protected(["clean", "done"], "CLEAN base with IDA") is True

    def test_no_match_returns_false(self, clean_snapshots):
        assert clean_snapshots.is_protected(["clean"], "Snapshot 1") is False

    def test_empty_protected_list_returns_false(self, clean_snapshots):
        assert clean_snapshots.is_protected([], "anything") is False


class TestGetSnapshotChildren:
    def test_returns_all_snapshots_when_no_root_given(self, clean_snapshots, monkeypatch):
        monkeypatch.setattr(clean_snapshots, "run_vboxmanage", lambda cmd, real_time=False: SNAPSHOTS_INFO)
        names = [name for name, _ in clean_snapshots.get_snapshot_children("VM", "", [])]
        assert names == ["ROOT", "Snapshot 1", "Snapshot 2", "Snapshot 3"]

    def test_returns_only_children_of_the_given_root(self, clean_snapshots, monkeypatch):
        monkeypatch.setattr(clean_snapshots, "run_vboxmanage", lambda cmd, real_time=False: SNAPSHOTS_INFO)
        names = [name for name, _ in clean_snapshots.get_snapshot_children("VM", "Snapshot 1", [])]
        assert names == ["Snapshot 1", "Snapshot 2"]

    def test_excludes_protected_snapshots(self, clean_snapshots, monkeypatch):
        monkeypatch.setattr(clean_snapshots, "run_vboxmanage", lambda cmd, real_time=False: SNAPSHOTS_INFO)
        names = [name for name, _ in clean_snapshots.get_snapshot_children("VM", "", ["snapshot 2"])]
        assert "Snapshot 2" not in names
        assert "Snapshot 1" in names

    def test_unknown_root_falls_back_to_all_snapshots(self, clean_snapshots, monkeypatch, capsys):
        monkeypatch.setattr(clean_snapshots, "run_vboxmanage", lambda cmd, real_time=False: SNAPSHOTS_INFO)
        names = [name for name, _ in clean_snapshots.get_snapshot_children("VM", "Nonexistent", [])]
        assert names == ["ROOT", "Snapshot 1", "Snapshot 2", "Snapshot 3"]
        assert "Root snapshot not found" in capsys.readouterr().out


class TestDeleteSnapshotAndChildren:
    def test_does_not_delete_when_user_declines(self, clean_snapshots, monkeypatch):
        monkeypatch.setattr(clean_snapshots, "run_vboxmanage", lambda cmd, real_time=False: SNAPSHOTS_INFO)
        monkeypatch.setattr(clean_snapshots, "get_vm_state", lambda vm: "poweroff")
        monkeypatch.setattr("builtins.input", lambda *_: "n")
        deleted = []
        # After confirmation the code would call run_vboxmanage with "delete"; capture any such call.
        orig = clean_snapshots.run_vboxmanage

        def spy(cmd, real_time=False):
            if "delete" in cmd:
                deleted.append(cmd)
            return orig(cmd, real_time)

        monkeypatch.setattr(clean_snapshots, "run_vboxmanage", spy)
        clean_snapshots.delete_snapshot_and_children("VM", "", [])
        assert deleted == []

    def test_deletes_children_in_reverse_when_confirmed(self, clean_snapshots, monkeypatch):
        monkeypatch.setattr(clean_snapshots, "get_vm_state", lambda vm: "poweroff")
        monkeypatch.setattr("builtins.input", lambda *_: "y")
        deleted_ids = []

        def fake(cmd, real_time=False):
            if "list" in cmd:
                return SNAPSHOTS_INFO
            if "delete" in cmd:
                deleted_ids.append(cmd[-1])

        monkeypatch.setattr(clean_snapshots, "run_vboxmanage", fake)
        clean_snapshots.delete_snapshot_and_children("VM", "Snapshot 1", [])
        # Children of "Snapshot 1" are [Snapshot 1, Snapshot 2]; deleted in reverse order.
        assert deleted_ids == ["uuid-1-1", "uuid-1"]

    def test_reports_protected_running_state_and_delete_errors(self, clean_snapshots, monkeypatch, capsys):
        monkeypatch.setattr(clean_snapshots, "get_vm_state", lambda vm: "running")
        monkeypatch.setattr("builtins.input", lambda *_: "y")

        def fake(cmd, real_time=False):
            if "list" in cmd:
                return SNAPSHOTS_INFO
            if "delete" in cmd:
                raise RuntimeError("cannot delete a snapshot with children")

        monkeypatch.setattr(clean_snapshots, "run_vboxmanage", fake)
        # protected_snapshots is truthy (prints the protected header) but matches nothing here.
        clean_snapshots.delete_snapshot_and_children("VM", "", ["important"])
        out = capsys.readouterr().out
        assert "won't be deleted" in out  # protected header printed
        assert "Snapshot deleting is slower" in out  # running-state warning printed
        assert "ERROR" in out  # delete failures reported, not raised
