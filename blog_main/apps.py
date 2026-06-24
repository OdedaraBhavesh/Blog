from django.apps import AppConfig


class BlogMainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blog_main'
    verbose_name = 'Blog Main'

    def ready(self):
        """Initialize Site framework on app startup."""
        import os
        # Only run on production/render to avoid double-running
        if os.environ.get('RENDER') == 'true':
            try:
                from django.contrib.sites.models import Site
                from django.db import connection
                from django.db.utils import OperationalError, ProgrammingError

                try:
                    # Only run if database is ready and sites table exists
                    if 'django_site' in connection.introspection.table_names():
                        # Ensure Site with ID=1 exists
                        site, created = Site.objects.get_or_create(
                            pk=1,
                            defaults={
                                'domain': 'blog-spno.onrender.com',
                                'name': 'Blog Sphere'
                            }
                        )

                        # Update domain if it's still default 'example.com'
                        if site.domain == 'example.com' or site.domain.startswith('127.0.0.1'):
                            site.domain = 'blog-spno.onrender.com'
                            site.name = 'Blog Sphere'
                            site.save()
                except (OperationalError, ProgrammingError):
                    # Database not ready yet (during migration phase)
                    pass
            except ImportError:
                # Sites app not installed
                pass
