from django.db.models import Q

# Filter for valid users (not superuser, not test account)
Q_VALID_USER = Q(is_superuser=False, is_test_account=False)

# Filter for objects related to a valid user via 'user' field
Q_VALID_USER_REL = Q(user__is_superuser=False, user__is_test_account=False)

# Filter for objects related to a valid user via 'belong_task__user'
Q_VALID_TASK_USER = Q(belong_task__user__is_superuser=False, belong_task__user__is_test_account=False)

# Filter for objects related to a valid user via 'belong_task_trial__belong_task__user'
Q_VALID_TRIAL_USER = Q(belong_task_trial__belong_task__user__is_superuser=False, belong_task_trial__belong_task__user__is_test_account=False)

# Tutorial dataset name (case-insensitive match)
TUTORIAL_DATASET_NAME = 'tutorial'

# Exclusion filters for tutorial datasets (use with .exclude())
# For Task model (via content__belong_dataset)
Q_TUTORIAL_TASK = Q(content__belong_dataset__name__iexact=TUTORIAL_DATASET_NAME)

# For objects related via belong_task (e.g., TaskTrial, annotations)
Q_TUTORIAL_TASK_REL = Q(belong_task__content__belong_dataset__name__iexact=TUTORIAL_DATASET_NAME)

# For objects related via belong_task_trial (e.g., Justification)
Q_TUTORIAL_TRIAL_REL = Q(belong_task_trial__belong_task__content__belong_dataset__name__iexact=TUTORIAL_DATASET_NAME)

# For Webpage model (via belong_task)
Q_TUTORIAL_WEBPAGE = Q(belong_task__content__belong_dataset__name__iexact=TUTORIAL_DATASET_NAME)
