"""Legal, policy, and info page views."""

from django.shortcuts import render


def privacy_policy(request):
    return render(request, 'legal.html', {
        'page_title': 'Privacy Policy',
        'meta_description': 'Privacy Policy for Nowhence Clothings — learn how we handle your data.',
        'content': """
<h2>1. Information We Collect</h2>
<p>When you use Nowhence Clothings, we may collect the following information:</p>
<ul>
    <li><strong>Personal Information:</strong> Name, email address, phone number, and shipping address when you create an account or place an order.</li>
    <li><strong>Payment Information:</strong> Payment details are processed securely through Razorpay. We do not store your card details on our servers.</li>
    <li><strong>Usage Data:</strong> Browser type, IP address, pages visited, and time spent on our site to improve your experience.</li>
    <li><strong>Cookies:</strong> We use cookies for session management, preferences, and analytics.</li>
</ul>

<h2>2. How We Use Your Information</h2>
<ul>
    <li>Processing and fulfilling your orders</li>
    <li>Communicating order updates via email and SMS</li>
    <li>Providing customer support</li>
    <li>Improving our website and services</li>
    <li>Sending promotional offers (you can opt out anytime)</li>
</ul>

<h2>3. Information Sharing</h2>
<p>We do not sell your personal data. We share information only with:</p>
<ul>
    <li><strong>Shipping Partners:</strong> To deliver your orders (e.g., Delhivery, BlueDart)</li>
    <li><strong>Payment Gateway:</strong> Razorpay processes payments securely</li>
    <li><strong>Legal Requirements:</strong> When required by law or regulation</li>
</ul>

<h2>4. Data Security</h2>
<p>We use industry-standard security measures including SSL encryption, secure payment processing, and access controls to protect your data.</p>

<h2>5. Your Rights</h2>
<p>You may request access to, correction of, or deletion of your personal data by emailing us at <a href="mailto:privacy@NowhenceClothings.com">privacy@NowhenceClothings.com</a>.</p>

<h2>6. Contact Us</h2>
<p>For privacy-related queries, contact us at <a href="mailto:privacy@NowhenceClothings.com">privacy@NowhenceClothings.com</a>.</p>
"""
    })


def terms_conditions(request):
    return render(request, 'legal.html', {
        'page_title': 'Terms & Conditions',
        'meta_description': 'Terms and Conditions for Nowhence Clothings online store.',
        'content': """
<h2>1. Acceptance of Terms</h2>
<p>By accessing or using Nowhence Clothings (nowhenceclothings.com), you agree to be bound by these Terms & Conditions. If you do not agree, please do not use our website.</p>

<h2>2. Products & Pricing</h2>
<ul>
    <li>All product images are representative. Actual colours may vary slightly due to screen settings and the handcrafted nature of our products.</li>
    <li>Prices are listed in Indian Rupees (₹) and include applicable GST.</li>
    <li>We reserve the right to modify prices without prior notice.</li>
</ul>

<h2>3. Orders & Payment</h2>
<ul>
    <li>Placing an order constitutes an offer to purchase. We reserve the right to accept or reject any order.</li>
    <li>Payment can be made via Razorpay (UPI, cards, net banking) or Cash on Delivery where available.</li>
    <li>Orders are confirmed only after successful payment verification.</li>
</ul>

<h2>4. User Accounts</h2>
<ul>
    <li>You are responsible for maintaining the confidentiality of your account credentials.</li>
    <li>You must provide accurate and complete information during registration.</li>
    <li>We reserve the right to suspend accounts that violate these terms.</li>
</ul>

<h2>5. Intellectual Property</h2>
<p>All content on this website — including designs, images, logos, and text — is the property of Nowhence Clothings and is protected by copyright laws. Unauthorized use is prohibited.</p>

<h2>6. Limitation of Liability</h2>
<p>Nowhence Clothings shall not be liable for any indirect, incidental, or consequential damages arising from the use of our website or products.</p>

<h2>7. Governing Law</h2>
<p>These terms are governed by the laws of India. Any disputes shall be subject to the exclusive jurisdiction of courts in New Delhi.</p>
"""
    })


def refund_policy(request):
    return render(request, 'legal.html', {
        'page_title': 'Refund & Return Policy',
        'meta_description': 'Refund and Return Policy for Nowhence Clothings — easy returns within 7 days.',
        'content': """
<h2>1. Return Window</h2>
<p>We accept returns within <strong>7 days</strong> of delivery. The product must be unused, unwashed, and in its original packaging with all tags attached.</p>

<h2>2. Eligible for Return</h2>
<ul>
    <li>Wrong product delivered</li>
    <li>Defective or damaged product</li>
    <li>Product significantly different from description</li>
    <li>Wrong size (exchange available)</li>
</ul>

<h2>3. Not Eligible for Return</h2>
<ul>
    <li>Products that have been worn, washed, or altered</li>
    <li>Products without original tags and packaging</li>
    <li>Sale or discounted items (unless defective)</li>
    <li>Customised or made-to-order products</li>
</ul>

<h2>4. Return Process</h2>
<ol>
    <li>Go to your <a href="/account/returns/">Returns & Exchanges</a> page</li>
    <li>Select the order and item you wish to return</li>
    <li>Choose return or exchange and state the reason</li>
    <li>Our team will review and schedule a pickup within 2-3 business days</li>
</ol>

<h2>5. Refund Timeline</h2>
<ul>
    <li><strong>Online payments:</strong> Refund credited to original payment method within 7-10 business days after we receive the returned product.</li>
    <li><strong>Cash on Delivery:</strong> Refund via bank transfer within 7-10 business days.</li>
</ul>

<h2>6. Exchanges</h2>
<p>Size exchanges are subject to availability. If the requested size is unavailable, a full refund will be processed.</p>
"""
    })


def shipping_policy(request):
    return render(request, 'legal.html', {
        'page_title': 'Shipping Policy',
        'meta_description': 'Shipping Policy for Nowhence Clothings — free shipping on orders above ₹5,000.',
        'content': """
<h2>1. Shipping Coverage</h2>
<p>We currently ship across India. International shipping is not available at this time. You can check delivery availability for your pincode on each product page.</p>

<h2>2. Shipping Charges</h2>
<ul>
    <li><strong>Free shipping</strong> on all orders above ₹5,000</li>
    <li><strong>₹199 flat rate</strong> for orders below ₹5,000</li>
    <li>Some remote pincodes may have additional shipping charges, which will be shown at checkout</li>
</ul>

<h2>3. Delivery Timeline</h2>
<ul>
    <li><strong>Metro cities:</strong> 3-5 business days</li>
    <li><strong>Other cities:</strong> 5-7 business days</li>
    <li><strong>Remote areas:</strong> 7-10 business days</li>
</ul>
<p>Delivery times may vary during sale seasons, festivals, and public holidays.</p>

<h2>4. Order Tracking</h2>
<p>Once your order is shipped, you will receive a tracking number via email. You can also track your order from the <a href="/account/track-order/">Track Order</a> page.</p>

<h2>5. Shipping Partners</h2>
<p>We ship via trusted logistics partners including Delhivery, BlueDart, and India Post to ensure safe and timely delivery.</p>

<h2>6. Damaged in Transit</h2>
<p>If your package arrives damaged, please contact us within 48 hours with photos of the damage. We will arrange a replacement or full refund.</p>
"""
    })
