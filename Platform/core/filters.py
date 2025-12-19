from django.db.models import Q

# Filter for valid users (not superuser, not test account)
Q_VALID_USER = Q(is_superuser=False, is_test_account=False)

# Filter for objects related to a valid user via 'user' field
Q_VALID_USER_REL = Q(user__is_superuser=False, user__is_test_account=False)

# Filter for objects related to a valid user via 'belong_task__user'
Q_VALID_TASK_USER = Q(belong_task__user__is_superuser=False, belong_task__user__is_test_account=False)

# Filter for objects related to a valid user via 'belong_task_trial__belong_task__user'
Q_VALID_TRIAL_USER = Q(belong_task_trial__belong_task__user__is_superuser=False, belong_task_trial__belong_task__user__is_test_account=False)
