# Cache rubric lookups for better performance
from django.core.cache import cache


from apps.rubrics.models import VettingRubric

def get_rubric_cached(rubric_id):
    """Get rubric with caching"""
    cache_key = f'rubric_{rubric_id}'
    rubric = cache.get(cache_key)
    
    if not rubric:
        rubric = VettingRubric.objects.select_related('created_by').prefetch_related('criteria').get(id=rubric_id)
        cache.set(cache_key, rubric, 3600)  # Cache for 1 hour
    
    return rubric

# Invalidate cache when rubric is updated
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=VettingRubric)
def invalidate_rubric_cache(sender, instance, **kwargs):
    cache_key = f'rubric_{instance.id}'
    cache.delete(cache_key)