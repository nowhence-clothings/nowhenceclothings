"""Email notification helpers for orders."""

import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def send_order_confirmation(order):
    """Send order confirmation email to customer."""
    if not order.user.email:
        return

    items_text = ''
    for item in order.items.all():
        items_text += f'  - {item.product_name} (×{item.quantity}) — ₹{item.total:,.0f}\n'

    discount_text = ''
    if order.discount_amount > 0:
        discount_text = f'Discount: -₹{order.discount_amount:,.0f}\n'

    message = f"""Hi {order.user.first_name or order.user.username},

Thank you for your order! Here are your order details:

Order Number: {order.order_number}
Payment: {order.get_payment_method_display()}

Items:
{items_text}
Subtotal: ₹{order.subtotal:,.0f}
{discount_text}Shipping: {'Free' if order.shipping_charge == 0 else f'₹{order.shipping_charge:,.0f}'}
Total: ₹{order.total:,.0f}

Shipping to:
{order.shipping_full_name}
{order.shipping_address}
{order.shipping_city}, {order.shipping_state} — {order.shipping_pincode}

You can track your order at: https://NowhenceClothings.com/account/track-order/?order_number={order.order_number}

Thank you for shopping with Nowhence Clothings!

— Nowhence Clothings
"""
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@NowhenceClothings.com')
        send_mail(
            subject=f'Order Confirmed — #{order.order_number} | Nowhence Clothings',
            message=message,
            from_email=from_email,
            recipient_list=[order.user.email],
            fail_silently=True,
        )
        logger.info(f'Order confirmation email sent for {order.order_number}')
    except Exception as e:
        logger.error(f'Failed to send order email for {order.order_number}: {e}')


def send_shipping_notification(order):
    """Send shipping update email when order status changes."""
    if not order.user.email:
        return

    status_messages = {
        'confirmed': 'Your order has been confirmed and is being prepared.',
        'shipped': f'Your order has been shipped! Tracking: {order.tracking_number or "Will be updated soon"}',
        'out_for_delivery': 'Your order is out for delivery. It should arrive today!',
        'delivered': 'Your order has been delivered. We hope you love it!',
        'cancelled': 'Your order has been cancelled. If you paid online, a refund will be processed within 7-10 business days.',
    }

    status_msg = status_messages.get(order.status)
    if not status_msg:
        return

    message = f"""Hi {order.user.first_name or order.user.username},

{status_msg}

Order: #{order.order_number}
Status: {order.get_status_display()}

Track your order: https://NowhenceClothings.com/account/track-order/?order_number={order.order_number}

— Nowhence Clothings
"""
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@nowhenceclothings.com')
        send_mail(
            subject=f'Order #{order.order_number} — {order.get_status_display()} | Nowhence Clothings',
            message=message,
            from_email=from_email,
            recipient_list=[order.user.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f'Failed to send shipping email for {order.order_number}: {e}')
