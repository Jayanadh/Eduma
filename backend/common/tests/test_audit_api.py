from common import audit

AUDIT = "/api/v1/platform/audit"


def test_audit_list_is_platform_only_and_filters(world, client_for):
    audit.log(world.platform_admin, "institution.updated", world.a, "Updated Aster School")
    audit.log(world.platform_admin, "institution.updated", world.b, "Updated Birch College")
    audit.log(world.a_admin, "site.published", world.a, "Published version 1 of Aster School's page")
    platform = client_for(None, world.platform_admin)
    everything = platform.get(AUDIT).json()
    assert everything["count"] == 3
    first = everything["results"][0]
    assert set(first) == {"id", "at", "actor_name", "institution_name", "action", "summary", "changes"}
    assert platform.get(AUDIT, {"action": "site."}).json()["count"] == 1
    assert platform.get(AUDIT, {"institution": str(world.b.id)}).json()["count"] == 1
    assert platform.get(AUDIT, {"search": "birch"}).json()["count"] == 1
    assert platform.get(AUDIT, {"search": world.a_admin.full_name}).json()["count"] == 1
    per_institution = platform.get(f"/api/v1/platform/institutions/{world.a.id}/audit").json()
    assert per_institution["count"] == 2
    assert client_for(world.a.slug, world.a_admin).get(AUDIT).status_code == 404
    assert client_for(None, world.a_admin).get(AUDIT).status_code == 403
