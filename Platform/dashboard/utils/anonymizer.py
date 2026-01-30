"""
User anonymization utilities for data export.
"""

from typing import Dict, Any, Optional

ANONYMIZED_PLACEHOLDER = "[ANONYMIZED]"

# Age range bins
AGE_BINS = [
    (0, 17, "under-18"),
    (18, 24, "18-24"),
    (25, 34, "25-34"),
    (35, 44, "35-44"),
    (45, 54, "45-54"),
    (55, 64, "55-64"),
    (65, 200, "65+"),
]


def get_age_range(age: Optional[int]) -> str:
    """Convert exact age to age range bin."""
    if age is None or age == 0:
        return ANONYMIZED_PLACEHOLDER
    for min_age, max_age, label in AGE_BINS:
        if min_age <= age <= max_age:
            return label
    return ANONYMIZED_PLACEHOLDER


class UserAnonymizer:
    """
    Handles user anonymization with consistent ID mapping.

    Usage:
        anonymizer = UserAnonymizer()
        anon_data = anonymizer.anonymize_user(user, profile)
    """

    def __init__(self):
        self._id_counter = 0
        self._id_map: Dict[int, str] = {}  # user.id -> anonymized_id

    def get_anonymized_id(self, user_id: int) -> str:
        """Get consistent anonymized ID for a user."""
        if user_id not in self._id_map:
            self._id_counter += 1
            self._id_map[user_id] = f"participant_{self._id_counter:06d}"
        return self._id_map[user_id]

    def anonymize_user(self, user, include_profile: bool = True) -> Dict[str, Any]:
        """
        Anonymize user data.

        Args:
            user: User model instance
            include_profile: Whether to include profile data

        Returns:
            Anonymized user dictionary
        """
        data = {
            "participant_id": self.get_anonymized_id(user.id),
            "username": ANONYMIZED_PLACEHOLDER,
            "email": ANONYMIZED_PLACEHOLDER,
            "first_name": ANONYMIZED_PLACEHOLDER,
            "last_name": ANONYMIZED_PLACEHOLDER,
            "date_joined": user.date_joined.isoformat() if user.date_joined else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "login_num": user.login_num,
            "consent_agreed": user.consent_agreed,
        }

        if include_profile and hasattr(user, 'profile'):
            data["profile"] = self.anonymize_profile(user.profile)

        return data

    def anonymize_profile(self, profile) -> Dict[str, Any]:
        """
        Anonymize profile data.

        Args:
            profile: Profile model instance

        Returns:
            Anonymized profile dictionary
        """
        return {
            "name": ANONYMIZED_PLACEHOLDER,
            "phone": ANONYMIZED_PLACEHOLDER,
            "age": get_age_range(profile.age),
            "gender": profile.gender,
            "occupation": profile.occupation,
            "education": profile.education,
            "field_of_expertise": ANONYMIZED_PLACEHOLDER,
            "icon": ANONYMIZED_PLACEHOLDER,
            "llm_frequency": profile.llm_frequency,
            "llm_history": profile.llm_history,
            "english_proficiency": profile.english_proficiency,
            "web_search_proficiency": profile.web_search_proficiency,
            "web_agent_familiarity": profile.web_agent_familiarity,
            "web_agent_frequency": profile.web_agent_frequency,
        }

    def export_user_full(self, user, include_profile: bool = True) -> Dict[str, Any]:
        """
        Export user data without anonymization (full mode).

        Args:
            user: User model instance
            include_profile: Whether to include profile data

        Returns:
            Full user dictionary
        """
        data = {
            "participant_id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "date_joined": user.date_joined.isoformat() if user.date_joined else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "login_num": user.login_num,
            "consent_agreed": user.consent_agreed,
        }

        if include_profile and hasattr(user, 'profile'):
            data["profile"] = self.export_profile_full(user.profile)

        return data

    def export_profile_full(self, profile) -> Dict[str, Any]:
        """
        Export profile data without anonymization (full mode).

        Args:
            profile: Profile model instance

        Returns:
            Full profile dictionary
        """
        return {
            "name": profile.name,
            "phone": profile.phone,
            "age": profile.age,
            "gender": profile.gender,
            "occupation": profile.occupation,
            "education": profile.education,
            "field_of_expertise": profile.field_of_expertise,
            "icon": str(profile.icon) if profile.icon else None,
            "llm_frequency": profile.llm_frequency,
            "llm_history": profile.llm_history,
            "english_proficiency": profile.english_proficiency,
            "web_search_proficiency": profile.web_search_proficiency,
            "web_agent_familiarity": profile.web_agent_familiarity,
            "web_agent_frequency": profile.web_agent_frequency,
        }
