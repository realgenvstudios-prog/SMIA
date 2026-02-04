'use client';

import { motion } from 'framer-motion';

export default function PrivacyPolicy() {
  return (
    <section className="py-24 px-4 md:px-8 lg:px-16 bg-gray-50 min-h-screen">
      <div className="max-w-4xl mx-auto bg-white rounded-2xl p-8 md:p-12 lg:p-16 shadow-sm">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mb-10">
            PRIVACY POLICY
          </h1>

          {/* Introduction */}
          <div className="mb-12 p-6 bg-gray-50 rounded-lg">
            <p className="text-gray-700 leading-relaxed">
              DWOM ("we", "us", "our") provides a platform for users to browse, purchase quality groceries and food products from DWOM and have them delivered to their doorstep ("Services"). At DWOM, one of our core values is transparency and we owe you ('User') a duty to tell you how we collect, use and share your personal information. Personal information means information that identifies you and includes information such as your name, email address, telephone number as well as any other personal data collected. We recommend that you read this Privacy Policy ("Policy") carefully to understand your rights and our duties towards managing your personal data in addition to our Terms of Use. If you have any questions about either of these documents, please send us an email at <a href="mailto:support@dwom.app" className="text-red-600 hover:text-red-700 underline">support@dwom.app</a>.
            </p>
          </div>

          {/* Section 1 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              1. Notification of Changes to Privacy Policy
            </h2>
            <p className="text-gray-700 leading-relaxed">
              This Privacy Policy will be reviewed annually to ensure compliance with applicable data protection laws and regulations in all jurisdictions where the Services are provided, including but not limited to Ghana's Data Protection Act 2012 (Act 843). Nonetheless, we are continually improving our methods of communication and adding new functionalities and features to our website and existing services. Because of these ongoing changes, changes in the law and the changing nature of technology, our data protection practices will change from time to time. If and when our data protection practices change, we will update this Policy to describe our new practices and publish them on our website and applications.
            </p>
          </div>

          {/* Section 2 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              2. Collecting your personal information
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              We are committed to informing and limiting the collection of essential personal information.
            </p>
            <p className="text-gray-700 leading-relaxed mb-4">We can get your personal information when you:</p>
            <ul className="text-gray-700 leading-relaxed space-y-1">
              <li>2.1. Browse or purchase groceries and food products from DWOM;</li>
              <li>2.2. Register for an account (such as registering your name, phone number, email address and physical address details);</li>
              <li>2.3. Subscribe to our regular delivery subscriptions or loyalty programs;</li>
              <li>2.4. Request customer support or contact us with a question or complaint;</li>
              <li>2.5. Rate products, delivery service, or provide feedback about your experience;</li>
              <li>2.6. Take part in a promotional offer, referral program, or survey;</li>
              <li>2.7. Use our mobile application and web platform;</li>
              <li>2.8. Visit or browse our website or mobile applications;</li>
              <li>2.9. With your permission or consent and/or as permitted by law, we may also collect information about you from other organizations or third parties if this is appropriate and allowed by law. These include fraud-prevention agencies, business directories, payment processors, and delivery logistics partners.</li>
            </ul>
          </div>

          {/* Section 3 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              3. Use and analysis of your personal information
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">We may use and analyse your information to:</p>
            <ul className="text-gray-700 leading-relaxed space-y-1">
              <li>3.1. Provide delivery Services, process orders, and facilitate transactions between you and our merchants;</li>
              <li>3.2. Connect you with the most suitable delivery riders in your area;</li>
              <li>3.3. Keep you informed generally about new products, services, promotions and merchant offerings (unless you choose not to receive our marketing messages);</li>
              <li>3.4. Understand how you use our network, products and services. That way, we can develop more interesting and relevant products and services and personalise the products and services we offer you;</li>
              <li>3.5. Comply with all applicable laws and regulations in Ghana;</li>
              <li>3.6. Develop, improve, enhance, modify, add to and further develop our services;</li>
              <li>3.7. Authenticate users, verify identity, and ensure that the data provided is credible;</li>
              <li>3.8. Prevent and detect fraud and illegal activities;</li>
              <li>3.9. Provide customer support services, including responding to your enquiries or complaints;</li>
              <li>3.10. Conduct customer surveys and research & development activities;</li>
              <li>3.11. Fulfil our obligations or claim our rights in legal proceedings;</li>
              <li>3.12. Process and facilitate payment for services and products provided on our platform;</li>
              <li>3.13. Respond to any questions or concerns you may have about using our products and services;</li>
              <li>3.14. Notify you about order status updates, delivery tracking, and delivery rider information;</li>
              <li>3.15. Manage and facilitate subscription services and recurring deliveries;</li>
              <li>3.16. Use or disclose it as otherwise authorised or permitted by law;</li>
              <li>3.17. Contact you at any time through your provided telephone number, email address or other contact;</li>
              <li>3.18. Provide aggregated reports to our merchants and partners to enable them to serve you better;</li>
              <li>3.19. For any other purpose with your consent.</li>
            </ul>
          </div>

          {/* Section 4 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              4. Consent
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              You accept this Notice when you sign our Consent Form or click on the "accept" button to opt-in and use any of our Platforms and Services or visit any of our offices for official or non-official purposes. You also consent to the collection and processing of your personal information (which includes but is not limited to your name, date of birth, email address, address, telephone number, payment information, etc), your order details, order history, ratings and reviews, and any other information for the purpose of providing the DWOM Services. If you decide to opt out of any of the DWOM Services or withdraw consent for the processing of your personal information, you can do so by reaching out to us at support@dwom.app or filling out our Data Subject Request Form. This Notice governs the use of the DWOM Services and if you are not comfortable with us processing your data, you may not use our Services.
            </p>
          </div>

          {/* Section 5 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              5. Third-Party Services
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              Occasionally, at our discretion, we may include or offer third-party products or services on our Platform. These third-party sites have separate and independent privacy policies. We therefore have no responsibility or liability for the content and activities of these linked sites. Nonetheless, we seek to protect the integrity of our Platform and welcome any feedback about these sites.
            </p>
            <p className="text-gray-700 leading-relaxed mb-4">
              We may also use third-party platforms such as Supabase, Paystack and Firebase for interactive information sharing and to connect with Users. We recommend that you read any terms and conditions (including any privacy statements or policies) that apply to any third-party web service relating to the handling and management of your personal information as they may use your personal information in ways and for purposes that are different from the way DWOM uses and processes your personal information.
            </p>
            <p className="text-gray-700 leading-relaxed">
              We encourage you to keep your personal information confidential by contacting them through direct or private messages, email or the customer service hotline.
            </p>
          </div>

          {/* Section 6 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              6. Storage and Security
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              We protect your information using physical, technical, and administrative security measures to reduce the risks of loss, misuse, and unauthorized access.
            </p>
            <p className="text-gray-700 leading-relaxed mb-4">
              Personal information is collected on servers in electronic databases which are located in secure data centres and managed by our related entities and/or service providers. We will ensure that your information is protected and that they only process your information in the way we have authorized them to. These organizations will not be entitled to use your personal information for their own purposes.
            </p>
            <p className="text-gray-700 leading-relaxed mb-4">
              We have put in place suitable physical, and electronic administrative procedures and measures to safeguard and protect the information about you that we collect, and to reduce the risks of loss, misuse, disclosure, alteration and unauthorised access to your personal information within our custody. Personal information and associated data stored on servers are encrypted and stored through data isolation technology.
            </p>
            <p className="text-gray-700 leading-relaxed mb-4">
              We limit access to personal information to individuals within our employ or that of our related entities or contracted service providers who we believe reasonably need access to such information to provide products or services to you, or to us, or to perform their duties. Some of the safeguards we use are firewalls and data encryption, physical access controls to our data centres, and information access authorization controls. To prevent unauthorised access to your information, we have implemented strong controls and security safeguards at the technical and operational levels. Our website uses a Secure Sockets Layer (SSL) to ensure secure transmission of your Personal Data. You should see the padlock symbol in your URL address bar when browsing through our website. The URL address will also start with https:// depicting a secure webpage. SSL applies encryption between two points such as your PC and the connecting server. Any data transmitted during the session will be encrypted before transmission and decrypted at the receiving end. This is to ensure that data cannot be read during transmission.
            </p>
            <p className="text-gray-700 leading-relaxed">
              We will never ask for your secure personal or account information by unsolicited means of communication. You are responsible for keeping your personal and account information secure and not sharing it with others. We shall not be liable for any unauthorised access or loss of personal information beyond our control.
            </p>
          </div>

          {/* Section 7 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              7. Retention period
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              The retention period for the personal information of users of DWOM shall be as follows:
            </p>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>7.1. Seven (7) years after the last active use of our digital platform;</li>
              <li>7.2. Upon presentation of evidence of death by a deceased's relative, personal information of such User would be discarded;</li>
              <li>7.3. Immediately upon request by the User of DWOM or his/her legal guardian where:</li>
            </ul>
            <ul className="text-gray-700 leading-relaxed space-y-1 ml-6">
              <li>a) No statutory provision states otherwise; and</li>
              <li>b) Such User is not the subject of an investigation or suit that may require retention of the personal information sought to be deleted.</li>
            </ul>
          </div>

          {/* Section 8 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              8. Access and corrections to personal information
            </h2>
            <p className="text-gray-700 leading-relaxed mb-4">
              8.1. Under the law, you have the right to access, correct, amend, and delete your personal information or object to processing your personal information.
            </p>
            <p className="text-gray-700 leading-relaxed mb-4">
              8.2. You may make any of the following requests in respect of your personal information within our custody:
            </p>
            <ul className="text-gray-700 leading-relaxed space-y-1 mb-4">
              <li>a) Confirmation on the personal information we hold about you;</li>
              <li>b) Access to the personal information we hold about you provided that such requests are made in compliance with the Freedom of Information Act and other applicable laws;</li>
              <li>c) Correction of or updates to the personal information we hold about you;</li>
              <li>d) Anonymization, blocking or erasure of your personal information that is no longer necessary for us to provide services to you or no longer necessary for our normal business operations and activities;</li>
              <li>e) Data portability. In some circumstances, you may, by express request ask us to provide a third-party service provider with a copy of the personal information we hold about you in a structured, machine-readable and commonly used format (as selected by us), or otherwise in accordance with the requirements of the applicable law;</li>
              <li>f) Deletion or erasure of personal information we hold about you, where we relied on your consent to use your personal information unless an exception applies, such as where we are required to retain such information to comply with our legal or regulatory obligations;</li>
              <li>g) Revoke your consent, where we rely on your consent to use and disclose your personal information.</li>
            </ul>
            <p className="text-gray-700 leading-relaxed mb-4">
              8.3. You can make any of the above requests by contacting us via email at support@dwom.app or filling out our Data Subject Request Form. We may ask you to provide suitable identification when you seek to make any of these requests, to verify your identity.
            </p>
            <p className="text-gray-700 leading-relaxed mb-4">
              8.4. We will provide you with a response as soon as possible. If we are unable to comply with your request for any reason (such as, not being permitted or required to do such an act under the privacy legislation in force), we will inform you of this.
            </p>
            <p className="text-gray-700 leading-relaxed mb-4">
              8.5. If the personal information we provide in response to your request includes information that is the personal information of a third party, or that is confidential, or in which we own the copyright (such as transcripts or recordings of customer service call records), we may redact such information where reasonably necessary, and you must keep such information confidential and not make the information public, including by sharing the information on social media, without our written consent sought and obtained.
            </p>
            <p className="text-gray-700 leading-relaxed mb-4">
              8.6. Users can also delete their accounts from the DWOM mobile application. If you delete your account, we will retain your personal information in accordance with our Retention Policy.
            </p>
            <p className="text-gray-700 leading-relaxed mb-4">
              8.7. DWOM may retain your personal information after you have requested us to delete or de-identify your information if:
            </p>
            <ul className="text-gray-700 leading-relaxed space-y-1 ml-6 mb-4">
              <li>a) There is an unresolved issue relating to your account, such as an outstanding credit on your account or an unresolved claim or dispute;</li>
              <li>b) We are required to by any applicable law; and/or</li>
              <li>c) Necessary for our legitimate business interests, such as fraud prevention and enhancing users' safety and security.</li>
            </ul>
            <p className="text-gray-700 leading-relaxed">
              8.8. When personal information is no longer required, we will take reasonable steps to delete personal information from our systems or de-identify personal information.
            </p>
          </div>

          {/* Section 9 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              9. Children's Privacy
            </h2>
            <p className="text-gray-700 leading-relaxed">
              Our Service is not intended for users under 18. We do not knowingly collect personal information from children. If we discover a child has provided personal information, we will delete it immediately.
            </p>
          </div>

          {/* Section 10 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              10. Changes to This Privacy Policy
            </h2>
            <p className="text-gray-700 leading-relaxed">
              We may update this Privacy Policy at any time. Changes will be effective immediately upon posting to the app. Your continued use of the Service constitutes acceptance of the updated Privacy Policy.
            </p>
          </div>

          {/* Section 11 */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              11. Contact Us
            </h2>
            <p className="text-gray-700 leading-relaxed">
              If you have any questions about this Privacy Policy, You can contact us:
            </p>
            <p className="text-gray-700 leading-relaxed mt-4">
              By email: <a href="mailto:support@dwom.app" className="text-red-600 hover:text-red-700 underline">support@dwom.app</a>
            </p>
          </div>

          <p className="text-gray-500 text-sm">
            Last reviewed in January 2026
          </p>
        </motion.div>
      </div>
    </section>
  );
}
