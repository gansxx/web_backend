"""
Subscription Database Operations

Handles all database operations for Stripe subscription management.
Uses Supabase RPC functions defined in the migration file.
"""

from center_management.db.base_config import BaseConfig
from loguru import logger
from postgrest.exceptions import APIError
from typing import Optional, Dict, Any, List
from datetime import datetime


class SubscriptionConfig(BaseConfig):
    """Subscription database configuration class"""

    def __init__(self):
        super().__init__()
        logger.info("Subscription config initialized")

    def insert_subscription(
        self,
        user_email: str,
        stripe_customer_id: str,
        stripe_subscription_id: str,
        stripe_price_id: str,
        status: str,
        current_period_start: datetime,
        current_period_end: datetime,
        trial_start: Optional[datetime] = None,
        trial_end: Optional[datetime] = None,
        plan_id: str = "monthly_subscription",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Insert new subscription record

        Args:
            user_email: User's email address
            stripe_customer_id: Stripe Customer ID
            stripe_subscription_id: Stripe Subscription ID
            stripe_price_id: Stripe Price ID
            status: Subscription status (trialing, active, etc.)
            current_period_start: Current billing period start
            current_period_end: Current billing period end
            trial_start: Trial period start (optional)
            trial_end: Trial period end (optional)
            plan_id: Internal plan identifier
            metadata: Additional metadata (optional)

        Returns:
            Subscription UUID or None if failed
        """
        try:
            params = {
                "p_user_email": user_email,
                "p_stripe_customer_id": stripe_customer_id,
                "p_stripe_subscription_id": stripe_subscription_id,
                "p_stripe_price_id": stripe_price_id,
                "p_status": status,
                "p_current_period_start": current_period_start.isoformat(),
                "p_current_period_end": current_period_end.isoformat(),
                "p_trial_start": trial_start.isoformat() if trial_start else None,
                "p_trial_end": trial_end.isoformat() if trial_end else None,
                "p_plan_id": plan_id,
                "p_metadata": metadata or {}
            }
            response = self.supabase.rpc("insert_subscription", params).execute()

            if response.data:
                logger.info(f"Inserted subscription: {stripe_subscription_id} for {user_email}")
                return response.data

            return None

        except APIError as e:
            logger.error(f"Failed to insert subscription: {e}")
            raise e

    def update_subscription_status(
        self,
        stripe_subscription_id: str,
        status: str,
        current_period_start: Optional[datetime] = None,
        current_period_end: Optional[datetime] = None,
        cancel_at_period_end: Optional[bool] = None,
        canceled_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
        cancel_at: Optional[datetime] = None,
        cancellation_details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update subscription status and period

        Args:
            stripe_subscription_id: Stripe Subscription ID
            status: New status
            current_period_start: New period start (optional)
            current_period_end: New period end (optional)
            cancel_at_period_end: Whether to cancel at period end (optional)
            canceled_at: When subscription was canceled (optional)
            ended_at: When subscription ended (optional)
            cancel_at: When subscription is scheduled to cancel (optional)
            cancellation_details: User feedback on cancellation (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            params = {
                "p_stripe_subscription_id": stripe_subscription_id,
                "p_status": status,
                "p_current_period_start": current_period_start.isoformat() if current_period_start else None,
                "p_current_period_end": current_period_end.isoformat() if current_period_end else None,
                "p_cancel_at_period_end": cancel_at_period_end,
                "p_canceled_at": canceled_at.isoformat() if canceled_at else None,
                "p_ended_at": ended_at.isoformat() if ended_at else None,
                "p_cancel_at": cancel_at.isoformat() if cancel_at else None,
                "p_cancellation_details": cancellation_details
            }
            response = self.supabase.rpc("update_subscription_status", params).execute()

            if response.data:
                logger.info(f"Updated subscription status: {stripe_subscription_id} -> {status}")
                if cancel_at:
                    logger.info(f"Subscription scheduled to cancel at: {cancel_at}")
                if cancellation_details:
                    logger.info(f"Cancellation details: {cancellation_details}")
                return True

            return False

        except APIError as e:
            logger.error(f"Failed to update subscription status: {e}")
            raise e

    def get_user_active_subscription(
        self,
        user_email: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get user's active subscription (trialing, active, or past_due)

        Args:
            user_email: User's email address

        Returns:
            Subscription dict or None if not found
        """
        try:
            params = {"p_user_email": user_email}
            response = self.supabase.rpc("get_user_active_subscription", params).execute()

            if response.data and len(response.data) > 0:
                return response.data[0]

            return None

        except APIError as e:
            logger.error(f"Failed to get active subscription for {user_email}: {e}")
            return None

    def get_subscription_by_stripe_id(
        self,
        stripe_subscription_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get subscription by Stripe subscription ID

        Args:
            stripe_subscription_id: Stripe Subscription ID

        Returns:
            Subscription dict or None if not found
        """
        try:
            params = {"p_stripe_subscription_id": stripe_subscription_id}
            response = self.supabase.rpc("get_subscription_by_stripe_id", params).execute()

            if response.data and len(response.data) > 0:
                return response.data[0]

            return None

        except APIError as e:
            logger.error(f"Failed to get subscription {stripe_subscription_id}: {e}")
            return None

    def mark_subscription_canceled(
        self,
        stripe_subscription_id: str,
        cancel_at_period_end: bool = True,
        canceled_at: Optional[datetime] = None
    ) -> bool:
        """
        Mark subscription as canceled

        Args:
            stripe_subscription_id: Stripe Subscription ID
            cancel_at_period_end: Whether to cancel at period end
            canceled_at: When subscription was canceled

        Returns:
            True if successful, False otherwise
        """
        try:
            params = {
                "p_stripe_subscription_id": stripe_subscription_id,
                "p_cancel_at_period_end": cancel_at_period_end,
                "p_canceled_at": canceled_at.isoformat() if canceled_at else None
            }
            response = self.supabase.rpc("mark_subscription_canceled", params).execute()

            if response.data:
                logger.info(f"Marked subscription canceled: {stripe_subscription_id}")
                return True

            return False

        except APIError as e:
            logger.error(f"Failed to mark subscription canceled: {e}")
            raise e

    def update_subscription_product(
        self,
        stripe_subscription_id: str,
        product_id: str
    ) -> bool:
        """
        Update subscription with generated product ID

        Args:
            stripe_subscription_id: Stripe Subscription ID
            product_id: Generated product UUID

        Returns:
            True if successful, False otherwise
        """
        try:
            params = {
                "p_stripe_subscription_id": stripe_subscription_id,
                "p_product_id": product_id
            }
            response = self.supabase.rpc("update_subscription_product", params).execute()

            if response.data:
                logger.info(f"Updated subscription product: {stripe_subscription_id} -> {product_id}")
                return True

            return False

        except APIError as e:
            logger.error(f"Failed to update subscription product: {e}")
            raise e

    def update_subscription_product_with_unique_name(
        self,
        stripe_subscription_id: str,
        product_id: str,
        unique_name: Optional[str] = None
    ) -> bool:
        """
        Update subscription with product_id and unique_name

        Args:
            stripe_subscription_id: Stripe Subscription ID
            product_id: Generated product UUID
            unique_name: Server-side unique identifier (email_timestamp format)

        Returns:
            True if successful, False otherwise
        """
        try:
            params = {
                "p_stripe_subscription_id": stripe_subscription_id,
                "p_product_id": product_id,
                "p_unique_name": unique_name
            }
            response = self.supabase.rpc("update_subscription_product_with_unique_name", params).execute()

            if response.data:
                logger.info(f"Updated subscription product with unique_name: {stripe_subscription_id} -> {product_id}, unique_name={unique_name}")
                return True

            return False

        except APIError as e:
            logger.error(f"Failed to update subscription product with unique_name: {e}")
            raise e

    def get_user_subscriptions(
        self,
        user_email: str
    ) -> List[Dict[str, Any]]:
        """
        Get all subscriptions for a user (including canceled)

        Args:
            user_email: User's email address

        Returns:
            List of subscription dicts
        """
        try:
            params = {"p_user_email": user_email}
            response = self.supabase.rpc("get_user_subscriptions", params).execute()

            return response.data or []

        except APIError as e:
            logger.error(f"Failed to get subscriptions for {user_email}: {e}")
            return []

    def check_user_has_active_subscription(
        self,
        user_email: str
    ) -> bool:
        """
        Check if user has an active subscription

        Args:
            user_email: User's email address

        Returns:
            True if user has active subscription, False otherwise
        """
        subscription = self.get_user_active_subscription(user_email)
        return subscription is not None


# Singleton instance for convenience
_subscription_config: Optional[SubscriptionConfig] = None


def get_subscription_config() -> SubscriptionConfig:
    """Get singleton instance of SubscriptionConfig"""
    global _subscription_config
    if _subscription_config is None:
        _subscription_config = SubscriptionConfig()
    return _subscription_config


# Export main interfaces
__all__ = [
    "SubscriptionConfig",
    "get_subscription_config",
]
