from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Case, When, IntegerField, Value
from .models import FriendRequest, Friendship

User = get_user_model()


class FriendSuggestionService:
    def __init__(self, user):
        self.user = user
        self._user_friends_ids = None
        self._exempted_users_ids = None

    @property
    def user_friends_ids(self):
        if self._user_friends_ids is None:
            self._user_friends_ids = list(
                Friendship.objects.filter(Q(user1=self.user) | Q(user2=self.user)).values_list(
                    Case(
                        When(user1=self.user, then="user2_id"),
                        default="user1_id",
                        output_field=IntegerField(),
                    ),
                    flat=True,
                )
            )

        return self._user_friends_ids

    @property
    def exempted_users_ids(self):
        if self._exempted_users_ids is None:
            self._exempted_users_ids = self._get_exempted_users_ids()

        return self._exempted_users_ids

    @property
    def _get_exempted_users_ids(self):
        pending_requests_users = list(
            FriendRequest.objects.filter(
                (Q(from_user=self.user) | Q(to_user=self.user)) & Q(status__in=["pending"]),  # "rejected"
            ).values_list("from_user_id", "to_user_id")
        )

        exempted_ids = set()
        for from_user_id, to_user_id in pending_requests_users:
            if from_user_id != self.user.id:
                exempted_ids.add(from_user_id)
            if to_user_id != self.user.id:
                exempted_ids.add(to_user_id)

        return list(exempted_ids)

    def get_suggestions(self, limit=20):
        if limit <= 0:
            return []

        suggestions = []
        seen_user_ids = set()

        if len(suggestions) < limit:
            remaining = limit - len(suggestions)
            random_suggestions = self._get_random_suggestions(remaining * 2)
            self._add_unique_suggestions(suggestions, random_suggestions, seen_user_ids, limit)

    def _get_base_queryset(self):
        return User.objects.exclude(id=self.user.id).exclude(id__in=self.user_friends_ids).exclude(id__in=self.exempted_users_ids)

    def _add_unique_suggestions(self, suggestions, new_suggestions, seen_user_ids, limit):
        for user in new_suggestions:
            if user.id not in seen_user_ids and len(suggestions) < limit:
                suggestions.append(user)
                seen_user_ids.add(user.id)
            elif len(suggestions) >= limit:
                break

    def _get_random_suggestions(self, limit):
        base_queryset = self._get_base_queryset().exclude(
            # exclude users already suggested by other strategies
            Q(friendships_as_user1__user2_id__in=self.user_friend_ids)
            | Q(friendships_as_user2__user1_id__in=self.user_friend_ids)
        )

        total_users = base_queryset.count()

        if total_users == 0:
            return []

        if total_users <= limit:
            return list(base_queryset.order_by("-created_at"))

        suggestions = base_queryset.order_by("?"[:limit])

        return list(suggestions)

    def clear_cache(self):
        self._user_friend_ids = None
        self._exempted_users_ids = None
