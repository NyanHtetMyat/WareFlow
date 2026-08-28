"""
accounts/signals.py
────────────────────────────────────────────────────────────────
Keeps profile-photo files on disk in sync with User.image, since
Django's ImageField does NOT do this automatically — replacing or
clearing an ImageField only ever updates the database row; the old
file is silently left behind in media/ unless something explicitly
deletes it. These two signal receivers are that "something."
"""

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import User


@receiver(pre_save, sender=User)
def delete_old_profile_photo_on_change(sender, instance, **kwargs):
    """
    Fires just before a User row is saved. If this is an EXISTING
    user (has a pk) whose stored image is about to change — either
    replaced with a different file or cleared entirely — the
    PREVIOUS file is deleted from storage first. This is what makes
    "replace image" and "remove image" both leave zero orphaned
    files behind.
    """
    if not instance.pk:
        return  # brand-new user being created — nothing to compare against yet

    try:
        previous_image = User.objects.get(pk=instance.pk).image
    except User.DoesNotExist:
        return

    if previous_image and previous_image != instance.image:
        previous_image.storage.delete(previous_image.name)


@receiver(post_delete, sender=User)
def delete_profile_photo_on_user_delete(sender, instance, **kwargs):
    """
    Fires after a User row is deleted. Cleans up that user's photo
    file too — rare in practice since Admins deactivate accounts
    rather than delete them, but this closes the gap for the cases
    where a User row genuinely is removed (e.g. via the shell).
    """
    if instance.image:
        instance.image.storage.delete(instance.image.name)