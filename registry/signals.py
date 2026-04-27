from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TrustEvent

@receiver(post_save, sender=TrustEvent)
def update_user_trust_scores(sender, instance, created, **kwargs):
    """
    Auto-updates User scores when a TrustEvent is created.
    If it's a penalty (points_delta < 0), we only update User.negative_score
    when mod_penalty_approved=True.
    """
    user = instance.user
    if created:
        if instance.points_delta > 0:
            user.positive_score += instance.points_delta
            user.save(update_fields=['positive_score'])
        # Penalties are handled via the update below when moderator approves them
    else:
        # On update (moderator approving a penalty)
        if instance.mod_penalty_approved and instance.points_delta < 0:
            user.negative_score += abs(instance.points_delta)
            user.save(update_fields=['negative_score'])
