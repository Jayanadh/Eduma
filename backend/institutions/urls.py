from rest_framework.routers import SimpleRouter

from institutions.views import PlatformInstitutionViewSet

router = SimpleRouter(trailing_slash=False)
router.register("institutions", PlatformInstitutionViewSet, basename="platform-institution")

platform_patterns = router.urls
