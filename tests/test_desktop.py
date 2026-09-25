from production_planner.desktop import bundled_database_path, resource_root


def test_desktop_resource_paths_resolve_in_repository():
    assert resource_root().name == "do-t"
    assert bundled_database_path().is_file()
