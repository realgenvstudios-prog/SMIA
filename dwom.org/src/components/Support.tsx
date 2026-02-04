'use client';

import { motion } from 'framer-motion';

export default function Support() {
  return (
    <>
      {/* Hero Section */}
      <section className="min-h-screen bg-gradient-to-br from-[#FF6B6B] to-[#FF5252] flex items-center justify-center py-20 px-4 md:px-8 lg:px-16 overflow-hidden">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-white mb-6 leading-tight">
              How Can We Help?
            </h1>
            
            <p className="text-lg md:text-xl lg:text-2xl text-white/95 max-w-3xl mx-auto leading-relaxed">
              Find answers to common questions or contact our support team
            </p>
          </motion.div>
        </div>
      </section>

      {/* Contact Options Section */}
      <section className="py-20 px-4 md:px-8 lg:px-16 bg-gray-50 overflow-hidden">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
            {/* Call Us */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="flex flex-col items-center text-center"
            >
              <div className="w-24 h-24 bg-red-100 rounded-full flex items-center justify-center mb-6">
                <span className="text-5xl">☎️</span>
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-4">
                Call Us
              </h3>
              <p className="text-xl font-semibold text-gray-900 mb-2">
                +233 50 224 3708
              </p>
              <p className="text-gray-600">
                Available within business hours
              </p>
            </motion.div>

            {/* Email Support */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1, duration: 0.6 }}
              className="flex flex-col items-center text-center"
            >
              <div className="w-24 h-24 bg-red-100 rounded-full flex items-center justify-center mb-6">
                <span className="text-5xl">✉️</span>
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-4">
                Email Support
              </h3>
              <p className="text-xl font-semibold text-gray-900 mb-2">
                <a href="mailto:support@dwom.app" className="hover:text-red-600 transition-colors">
                  support@dwom.app
                </a>
              </p>
              <p className="text-gray-600">
                Response in less than 12 hours
              </p>
            </motion.div>

            {/* Business Hours */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.2, duration: 0.6 }}
              className="flex flex-col items-center text-center"
            >
              <div className="w-24 h-24 bg-red-100 rounded-full flex items-center justify-center mb-6">
                <span className="text-5xl">🕐</span>
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-4">
                Business Hours
              </h3>
              <p className="text-xl font-semibold text-gray-900 mb-2">
                Mon-Sun 9 AM - 11 PM
              </p>
              <p className="text-gray-600">
                Extended support available
              </p>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Contact Form Section */}
      <section className="py-20 px-4 md:px-8 lg:px-16 bg-white overflow-hidden">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              Didn't Find What You Need?
            </h2>
          </motion.div>

          <form className="space-y-6">
            {/* Name and Email Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1, duration: 0.6 }}
              >
                <label className="block text-lg font-semibold text-gray-900 mb-2">
                  Full Name
                </label>
                <input
                  type="text"
                  placeholder="Your name"
                  className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:outline-none focus:border-red-600 text-gray-700 placeholder-gray-400"
                />
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.15, duration: 0.6 }}
              >
                <label className="block text-lg font-semibold text-gray-900 mb-2">
                  Email Address
                </label>
                <input
                  type="email"
                  placeholder="You@email.com"
                  className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:outline-none focus:border-red-600 text-gray-700 placeholder-gray-400"
                />
              </motion.div>
            </div>

            {/* Subject */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.2, duration: 0.6 }}
            >
              <label className="block text-lg font-semibold text-gray-900 mb-2">
                Subject
              </label>
              <input
                type="text"
                placeholder="How can we help you?"
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:outline-none focus:border-red-600 text-gray-700 placeholder-gray-400"
              />
            </motion.div>

            {/* Message */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.25, duration: 0.6 }}
            >
              <label className="block text-lg font-semibold text-gray-900 mb-2">
                Message
              </label>
              <textarea
                placeholder="Tell us more about your issue...."
                rows={8}
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:outline-none focus:border-red-600 text-gray-700 placeholder-gray-400 resize-none"
              />
            </motion.div>

            {/* Submit Button */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.3, duration: 0.6 }}
            >
              <button
                type="submit"
                className="w-full bg-red-600 hover:bg-red-700 text-white font-semibold py-3 rounded-lg transition-all duration-300 text-lg"
              >
                Send Message
              </button>
            </motion.div>
          </form>
        </div>
      </section>
    </>
  );
}
