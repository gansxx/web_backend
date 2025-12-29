"""
Stripe Subscription Integration Module

Handles:
- Creating subscription checkout sessions with trial period (dynamic product creation)
- Managing subscription lifecycle (cancel, update)
- Customer portal session creation

Configuration:
- SUBSCRIPTION_TRIAL_DAYS: Trial period in days (default: 30)

Usage:
    # Create subscription checkout with dynamic pricing
    result = StripeSubscriptionService.create_subscription_checkout_session(
        customer_email="user@example.com",
        amount_cents=999,           # $9.99
        currency="usd",
        product_name="Premium Monthly",
        interval="month",           # month | year | week | day
        trial_days=30,
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
    )
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import stripe
from loguru import logger

# Stripe API Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")

# Subscription Configuration
SUBSCRIPTION_TRIAL_DAYS = int(os.getenv("SUBSCRIPTION_TRIAL_DAYS", "30"))

# Initialize Stripe at module level if key available
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
    logger.debug(f"Stripe API key loaded at module level: {STRIPE_SECRET_KEY[:15]}...")


@dataclass
class SubscriptionCheckoutRequest:
    """Subscription checkout request data (dynamic product creation)"""
    customer_email: str
    success_url: str
    cancel_url: str
    amount_cents: int              # Price in cents (e.g., 999 = $9.99)
    currency: str                  # ISO currency code (e.g., 'usd', 'cny')
    product_name: str              # Product name (e.g., 'Premium Monthly')
    interval: str = "month"        # Billing interval: 'day' | 'week' | 'month' | 'year'
    trial_days: int = 30
    plan_id: str = "subscription"
    metadata: Optional[Dict[str, str]] = None


class StripeSubscriptionService:
    """Stripe Subscription Service"""

    @staticmethod
    def _ensure_api_key() -> None:
        """Ensure Stripe API key is set"""
        if not stripe.api_key:
            api_key = os.getenv("STRIPE_SECRET_KEY")
            if api_key:
                stripe.api_key = api_key
                logger.info("Stripe API key loaded dynamically")
            else:
                logger.warning("STRIPE_SECRET_KEY environment variable not set")

    @staticmethod
    def create_subscription_checkout_session(
        customer_email: str,
        success_url: str,
        cancel_url: str,
        amount_cents: int,
        currency: str,
        product_name: str,
        interval: str = "month",
        trial_days: int = 30,
        plan_id: str = "subscription",
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Create a Checkout Session for subscription with trial period (dynamic product creation)

        Stripe will require card binding but won't charge until trial ends.
        Product and Price are created dynamically - no need to pre-create in Dashboard.

        Args:
            customer_email: Customer email address
            success_url: URL to redirect after successful checkout
            cancel_url: URL to redirect if checkout is canceled
            amount_cents: Subscription price in cents (e.g., 999 = $9.99)
            currency: ISO currency code (e.g., 'usd', 'cny')
            product_name: Product name displayed to customer
            interval: Billing interval - 'day' | 'week' | 'month' | 'year'
            trial_days: Trial period in days (default: 30)
            plan_id: Internal plan identifier
            metadata: Additional metadata to attach

        Returns:
            Dict with success status and checkout session details
        """
        StripeSubscriptionService._ensure_api_key()

        try:
            session_metadata = metadata or {}
            session_metadata["plan_id"] = plan_id
            session_metadata["customer_email"] = customer_email

            # Use price_data for dynamic product/price creation
            line_items = [{
                'price_data': {
                    'currency': currency.lower(),
                    'product_data': {
                        'name': product_name,
                    },
                    'unit_amount': amount_cents,
                    'recurring': {
                        'interval': interval,
                    },
                },
                'quantity': 1,
            }]

            session = stripe.checkout.Session.create(
                mode='subscription',
                line_items=line_items,
                customer_email=customer_email,
                success_url=success_url,
                cancel_url=cancel_url,
                subscription_data={
                    'trial_period_days': trial_days,
                    'metadata': session_metadata,
                },
                payment_method_types=['card'],
                metadata=session_metadata,
            )

            logger.info(
                f"Created subscription checkout session: {session.id} "
                f"for {product_name} at {amount_cents} {currency.upper()}/{'mo' if interval == 'month' else interval} "
                f"with {trial_days} days trial"
            )

            return {
                "success": True,
                "checkout_session_id": session.id,
                "checkout_url": session.url
            }

        except stripe.StripeError as e:
            logger.error(f"Failed to create subscription checkout: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def cancel_subscription(
        subscription_id: str,
        at_period_end: bool = True
    ) -> Dict[str, Any]:
        """
        Cancel subscription

        Args:
            subscription_id: Stripe subscription ID
            at_period_end: If True (default), cancel at period end
                          If False, cancel immediately

        Returns:
            Dict with success status and subscription details
        """
        StripeSubscriptionService._ensure_api_key()

        try:
            if at_period_end:
                # Cancel at period end - service continues until period ends
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
                logger.info(f"Subscription {subscription_id} marked for cancellation at period end")
            else:
                # Immediate cancellation
                subscription = stripe.Subscription.cancel(subscription_id)
                logger.info(f"Subscription {subscription_id} canceled immediately")

            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "current_period_end": subscription.current_period_end
            }

        except stripe.StripeError as e:
            logger.error(f"Failed to cancel subscription {subscription_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def get_subscription(subscription_id: str) -> Optional[stripe.Subscription]:
        """
        Retrieve subscription details from Stripe

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Stripe Subscription object or None if failed
        """
        StripeSubscriptionService._ensure_api_key()

        try:
            return stripe.Subscription.retrieve(subscription_id)
        except stripe.StripeError as e:
            logger.error(f"Failed to retrieve subscription {subscription_id}: {e}")
            return None

    @staticmethod
    def create_customer_portal_session(
        customer_id: str,
        return_url: str
    ) -> Dict[str, Any]:
        """
        Create Stripe Customer Portal session for subscription management

        Users can manage their subscription through this portal:
        - View subscription details
        - Update payment method
        - Cancel subscription

        Args:
            customer_id: Stripe Customer ID
            return_url: URL to redirect after portal session

        Returns:
            Dict with success status and portal URL
        """
        StripeSubscriptionService._ensure_api_key()

        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )

            logger.info(f"Created customer portal session for customer: {customer_id}")

            return {
                "success": True,
                "portal_url": session.url
            }

        except stripe.StripeError as e:
            logger.error(f"Failed to create portal session for customer {customer_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def reactivate_subscription(subscription_id: str) -> Dict[str, Any]:
        """
        Reactivate a subscription that was marked for cancellation

        Only works if cancel_at_period_end was True and period hasn't ended

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Dict with success status and subscription details
        """
        StripeSubscriptionService._ensure_api_key()

        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False
            )

            logger.info(f"Subscription {subscription_id} reactivated")

            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "cancel_at_period_end": subscription.cancel_at_period_end
            }

        except stripe.StripeError as e:
            logger.error(f"Failed to reactivate subscription {subscription_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def get_customer_subscriptions(customer_id: str) -> Dict[str, Any]:
        """
        Get all subscriptions for a customer

        Args:
            customer_id: Stripe Customer ID

        Returns:
            Dict with success status and list of subscriptions
        """
        StripeSubscriptionService._ensure_api_key()

        try:
            subscriptions = stripe.Subscription.list(
                customer=customer_id,
                limit=10
            )

            return {
                "success": True,
                "subscriptions": [
                    {
                        "id": sub.id,
                        "status": sub.status,
                        "current_period_start": sub.current_period_start,
                        "current_period_end": sub.current_period_end,
                        "cancel_at_period_end": sub.cancel_at_period_end,
                        "trial_end": sub.trial_end
                    }
                    for sub in subscriptions.data
                ]
            }

        except stripe.StripeError as e:
            logger.error(f"Failed to get subscriptions for customer {customer_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def update_subscription_price(
        subscription_id: str,
        new_price_id: str,
        proration_behavior: str = "none"
    ) -> Dict[str, Any]:
        """
        Update subscription price (for downgrade)

        Args:
            subscription_id: Stripe subscription ID
            new_price_id: New Stripe Price ID
            proration_behavior: 'none' = takes effect at period end (default)
                               'create_prorations' = immediate with proration

        Returns:
            Dict with success status and updated subscription details
        """
        StripeSubscriptionService._ensure_api_key()

        try:
            subscription = stripe.Subscription.retrieve(subscription_id)

            updated = stripe.Subscription.modify(
                subscription_id,
                items=[{
                    'id': subscription['items']['data'][0].id,
                    'price': new_price_id,
                }],
                proration_behavior=proration_behavior
            )

            logger.info(f"Updated subscription {subscription_id} to price {new_price_id}")

            return {
                "success": True,
                "subscription_id": updated.id,
                "status": updated.status
            }

        except stripe.StripeError as e:
            logger.error(f"Failed to update subscription {subscription_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Export main interfaces
__all__ = [
    "StripeSubscriptionService",
    "SubscriptionCheckoutRequest",
    "SUBSCRIPTION_TRIAL_DAYS",
]
