'use client';

import { motion } from 'framer-motion';

export default function TermsAndConditions() {
  return (
    <section className="py-24 px-4 md:px-8 lg:px-16 bg-gray-50 min-h-screen">
      <div className="max-w-4xl mx-auto bg-white rounded-2xl p-8 md:p-12 lg:p-16 shadow-sm">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mb-12">
            TERMS AND CONDITIONS
          </h1>

          {/* Section 1 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              1. Acceptance of Terms
            </h2>
            <p className="text-gray-700 leading-relaxed">
              By accessing and using DWOM ("Platform," "we," "us," "our"), you agree to be bound by these Terms and Conditions, our Privacy Policy, and all applicable laws. If you do not agree, do not use this Platform.
            </p>
          </div>

          {/* Section 2 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              2. Eligibility
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">You must be:</p>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>At least 18 years old</li>
              <li>A legal resident of Ghana</li>
              <li>Able to enter into a binding contract</li>
              <li>Not prohibited by law from using our services</li>
            </ul>
            <p className="text-gray-700 leading-relaxed">
              We reserve the right to verify age and eligibility at any time.
            </p>
          </div>

          {/* Section 3 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              3. User Accounts
            </h2>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Registration Requirements:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>You are responsible for maintaining the confidentiality of your account credentials</li>
              <li>You agree to provide accurate, complete information during registration</li>
              <li>You are liable for all activities under your account</li>
              <li>You must notify us immediately of unauthorized access</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Account Termination:</h3>
            <p className="text-gray-700 leading-relaxed mb-2">We may suspend or terminate your account if you:</p>
            <ul className="text-gray-700 leading-relaxed space-y-1">
              <li>Violate these Terms</li>
              <li>Engage in fraudulent or illegal activity</li>
              <li>Provide false information</li>
              <li>Abuse the Platform or other users</li>
            </ul>
          </div>

          {/* Section 4 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              4. Orders and Purchases
            </h2>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Order Placement:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>Orders are submitted subject to acceptance by both merchants and DWOM</li>
              <li>We reserve the right to refuse or cancel any order</li>
              <li>Orders are binding once confirmed by the merchant</li>
              <li>Product availability is not guaranteed</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Pricing:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>Prices are in Ghana Cedis (GHS)</li>
              <li>Prices are subject to change without notice</li>
              <li>All prices include applicable taxes unless otherwise stated</li>
              <li>Delivery fees are calculated based on distance and location</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Order Confirmation:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1">
              <li>A confirmation email/SMS will be sent after order placement</li>
              <li>Order status updates will be sent via app notifications, SMS, and email</li>
            </ul>
          </div>

          {/* Section 5 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              5. Payment
            </h2>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Payment Methods:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>We accept mobile money, credit/debit cards, and bank transfers</li>
              <li>Payments are processed securely through third-party providers</li>
              <li>You authorize DWOM to charge your chosen payment method</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Billing:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>You are responsible for all charges to your account</li>
              <li>Failed payments may result in order cancellation</li>
              <li>Refunds (if applicable) will be credited to the original payment method</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Disputed Charges:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1">
              <li>Report disputed charges within 30 days of the transaction</li>
              <li>We will investigate and respond within 7 business days</li>
              <li>DWOM is not liable for merchant payment errors</li>
            </ul>
          </div>

          {/* Section 6 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              6. Delivery and Delivery Riders
            </h2>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Delivery Service:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>DWOM manages order fulfillment and delivery</li>
              <li>Delivery timeframes are estimates, not guarantees</li>
              <li>We are not responsible for delays due to merchant preparation or traffic</li>
              <li>Delivery is to the address you provided at checkout</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Delivery Riders:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>Riders operate as independent contractors</li>
              <li>DWOM is not responsible for rider actions beyond our explicit policies</li>
              <li>Riders are subject to safety and conduct standards</li>
              <li>Report unsafe or inappropriate rider behavior to support@dwom.app</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Lost or Damaged Orders:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1">
              <li>Report issues within 24 hours of delivery via the app</li>
              <li>We will investigate and provide compensation if warranted</li>
              <li>DWOM is not liable for merchant packaging quality</li>
              <li>Refunds are at DWOM's discretion after investigation</li>
            </ul>
          </div>

          {/* Section 7 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              7. Cancellations and Refunds
            </h2>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Order Cancellation:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>Orders can only be cancelled before the merchant begins preparation</li>
              <li>Cancellation requests must be submitted through the app</li>
              <li>Cancellation fees may apply (displayed before confirmation)</li>
              <li>DWOM processes cancellations within 2-3 business days</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Refund Policy:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>Approved refunds are credited to your original payment method</li>
              <li>Refunds are processed within 5-7 business days</li>
              <li>DWOM is not responsible for delays from your financial institution</li>
              <li>Merchants may withhold refunds for items already prepared</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Non-Refundable Items:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1">
              <li>Partially consumed or damaged items</li>
              <li>Items not matching the order description due to customer error</li>
              <li>Orders eligible for promotional pricing (if terms specify)</li>
            </ul>
          </div>

          {/* Section 8 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              8. Merchant and Product Information
            </h2>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Merchant Responsibility:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>Merchants are responsible for order accuracy and product quality</li>
              <li>DWOM does not guarantee merchant representations</li>
              <li>Merchants are independent third parties, not DWOM employees</li>
              <li>File complaints about merchants directly through the Platform</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Product Liability:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1">
              <li>DWOM is not liable for defective, expired, or misrepresented products</li>
              <li>Complaints must be filed within 48 hours of delivery</li>
              <li>Contact the merchant directly for quality issues</li>
              <li>DWOM may escalate complaints to regulatory authorities</li>
            </ul>
          </div>

          {/* Section 9 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              9. Subscription
            </h2>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Subscription Plans:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>Weekly, bi-weekly, and monthly subscription options are available</li>
              <li>Subscriptions automatically renew at the end of each billing cycle</li>
              <li>Bonus products are included as specified in your plan</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Subscription Changes:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>You can upgrade, downgrade, or cancel anytime</li>
              <li>Changes take effect at the start of the next billing cycle</li>
              <li>No refunds for unused days in the current cycle</li>
              <li>Cancellation via app or email to support@dwom.app</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Failed Payment:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1">
              <li>If payment fails, we will retry within 7 days</li>
              <li>If retries fail, your subscription is automatically paused</li>
              <li>Reactivate by updating your payment method</li>
              <li>We are not responsible for service interruptions due to payment failure</li>
            </ul>
          </div>

          {/* Section 10 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              10. User Conduct
            </h2>
            <p className="text-gray-700 leading-relaxed mb-2">You agree not to:</p>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>Post illegal, offensive, or inappropriate content</li>
              <li>Harass, threaten, or abuse other users, merchants, or riders</li>
              <li>Engage in fraudulent transactions or payment disputes</li>
              <li>Use automated tools or bots to access the Platform</li>
              <li>Attempt to gain unauthorized access to our systems</li>
              <li>Resell or redistribute our services</li>
              <li>Use the Platform for commercial purposes without permission</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Violations:</h3>
            <p className="text-gray-700 leading-relaxed mb-2">Violations may result in:</p>
            <ul className="text-gray-700 leading-relaxed space-y-1">
              <li>Content removal or account suspension</li>
              <li>Permanent account termination</li>
              <li>Legal action</li>
              <li>Reporting to law enforcement</li>
            </ul>
          </div>

          {/* Section 11 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              11. Limitation of Liability
            </h2>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">DWOM's Liability is Limited to:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>Refunds for direct damages caused by DWOM's negligence</li>
              <li>Maximum refund: the order amount plus delivery fee</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">DWOM is Not Liable for:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1">
              <li>Merchant product quality or accuracy</li>
              <li>Delivery delays or failed deliveries</li>
              <li>Third-party payment processor errors</li>
              <li>Losses due to technical issues or service interruptions</li>
              <li>Indirect, incidental, or consequential damages</li>
              <li>Lost profits or business opportunities</li>
              <li>Rider actions beyond DWOM's explicit policies</li>
            </ul>
          </div>

          {/* Section 12 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              12. Intellectual Property
            </h2>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">DWOM Content:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>All logos, text, images, code, and design are DWOM's property</li>
              <li>You may not copy, modify, or distribute Platform content</li>
              <li>Unauthorized use is a violation of intellectual property laws</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">User Content:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1">
              <li>You grant DWOM a non-exclusive license to use your ratings, reviews, and feedback</li>
              <li>DWOM may display your content on the Platform and in marketing</li>
              <li>You retain ownership of your content</li>
            </ul>
          </div>

          {/* Section 13 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              13. Disputes and Dispute Resolution
            </h2>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Dispute Reporting:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>Report disputes within 30 days of the incident</li>
              <li>Provide order details, evidence, and explanation</li>
              <li>Submit disputes through the app or email support@dwom.app</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Resolution Process:</h3>
            <ol className="text-gray-700 leading-relaxed space-y-1 mb-4 list-decimal list-inside">
              <li>DWOM investigates within 5 business days</li>
              <li>We contact you with our findings</li>
              <li>If you disagree, request escalation within 14 days</li>
              <li>Final decision is made within 30 days of escalation</li>
            </ol>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Unresolved Disputes:</h3>
            <ul className="text-gray-700 leading-relaxed space-y-1">
              <li>If unresolved after 30 days, either party may pursue legal action</li>
              <li>Disputes are governed by Ghana law (see Section 14)</li>
            </ul>
          </div>

          {/* Section 14 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              14. Limitation Period
            </h2>
            <p className="text-gray-700 leading-relaxed">
              You must bring any claim against DWOM within one (1) year of when the claim arose. Claims filed after this period are barred.
            </p>
          </div>

          {/* Section 15 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              15. Changes to Terms
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              DWOM may update these Terms at any time. Changes take effect when published on the Platform. Continued use after changes constitutes acceptance of the new Terms.
            </p>
            <p className="text-gray-700 leading-relaxed">
              We will notify you of material changes via email or in-app notification when possible.
            </p>
          </div>

          {/* Section 16 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              16. Governing Law
            </h2>
            <p className="text-gray-700 leading-relaxed">
              These Terms are governed by the laws of the Republic of Ghana, without regard to conflicts of law principles.
            </p>
          </div>

          {/* Section 17 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              17. Contact Information
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">For questions or disputes, contact us:</p>
            <ul className="text-gray-700 leading-relaxed space-y-2">
              <li>📧 Email: support@dwom.app</li>
              <li>📞 Phone: [Support Number]</li>
              <li>🌐 Website: [DWOM Website]</li>
            </ul>
          </div>

          {/* Important Notice */}
          <div className="mb-10 p-6 bg-gray-100 rounded-lg">
            <p className="text-gray-700 leading-relaxed font-medium">
              Important: These Terms and our Privacy Policy constitute the entire agreement between you and DWOM regarding the Platform. If any provision is found invalid, the remaining provisions remain enforceable.
            </p>
          </div>

          <p className="text-gray-700 leading-relaxed mb-6">
            By using DWOM, you acknowledge that you have read, understood, and agree to be bound by these Terms and Conditions.
          </p>

          <p className="text-gray-500 text-sm">
            Last reviewed in January 2026
          </p>
        </motion.div>
      </div>
    </section>
  );
}
