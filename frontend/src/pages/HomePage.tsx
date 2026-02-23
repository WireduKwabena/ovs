// src/pages/HomePage.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Shield, 
  FileCheck, 
  Zap, 
  Lock, 
  CheckCircle, 
  ArrowRight,
  Users,
  // BarChart3,
  Clock
} from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';


export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const features = [
    {
      icon: Shield,
      title: 'AI-Powered Verification',
      description: 'Advanced machine learning algorithms verify document authenticity with 95%+ accuracy',
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
    },
    {
      icon: FileCheck,
      title: 'Multi-Document Support',
      description: 'Upload and verify multiple document types including IDs, certificates, and credentials',
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
    {
      icon: Zap,
      title: 'Fast Processing',
      description: 'Get verification results in minutes, not days. Automated workflows speed up the process',
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-100',
    },
    {
      icon: Lock,
      title: 'Secure & Compliant',
      description: 'Bank-level encryption and GDPR-compliant data handling ensure your information is safe',
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
    },
  ];

  const stats = [
    { label: 'Applications Processed', value: '10,000+', icon: FileCheck },
    { label: 'Verification Accuracy', value: '95%', icon: CheckCircle },
    { label: 'Average Processing Time', value: '2.5 days', icon: Clock },
    { label: 'Active Users', value: '5,000+', icon: Users },
  ];

  const howItWorks = [
    {
      step: '1',
      title: 'Create Account',
      description: 'Sign up in minutes with your email and basic information',
    },
    {
      step: '2',
      title: 'Submit Application',
      description: 'Upload your documents and fill out the required information',
    },
    {
      step: '3',
      title: 'AI Verification',
      description: 'Our AI system analyzes and verifies your documents automatically',
    },
    {
      step: '4',
      title: 'Get Results',
      description: 'Receive your verification results and proceed with confidence',
    },
  ];

  return (
    <div className="min-h-screen bg-linear-to-b from-gray-50 to-white">
      {/* Navigation */}
      <nav className="bg-white shadow-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <Shield className="w-8 h-8 text-indigo-600" />
              <span className="ml-2 text-2xl font-bold text-gray-900">VettingSystem</span>
            </div>
            <div className="flex items-center gap-4">
              {isAuthenticated ? (
                <button
                type='button'
                  onClick={() => navigate('/dashboard')}
                  className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium transition-colors"
                >
                  Go to Dashboard
                </button>
              ) : (
                <>
                  <button
                  type='button'
                    onClick={() => navigate('/login')}
                    className="px-6 py-2 text-gray-400 hover:text-indigo-400 font-medium transition-colors"
                  >
                    Sign In
                  </button>
                  <button
                  type='button'
                    onClick={() => navigate('/register')}
                    className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium transition-colors"
                  >
                    Get Started
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
          <div className="text-center">
            <h1 className="text-5xl md:text-6xl font-extrabold text-gray-900 mb-6">
              AI-Powered Document
              <span className="block text-indigo-600">Vetting & Verification</span>
            </h1>
            <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto">
              Streamline your background checks and credential verification with cutting-edge 
              artificial intelligence. Fast, accurate, and secure.
            </p>
            <div className="flex gap-4 justify-center">
              <button
              type='button'
                onClick={() => navigate('/register')}
                className="inline-flex items-center gap-2 px-8 py-4 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-semibold text-lg transition-all hover:scale-105"
              >
                Start Verification
                <ArrowRight className="w-5 h-5" />
              </button>
              <button
                onClick={() => navigate('/login')}
                type='button'
                className="px-8 py-4 border-2 border-indigo-600 text-indigo-600 rounded-lg hover:bg-indigo-50 font-semibold text-lg transition-colors"
              >
                Learn More
              </button>
            </div>
          </div>

          {/* Decorative elements */}
          <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10">
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse"></div>
            <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse delay-1000"></div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 bg-indigo-600">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map((stat, index) => (
              <div key={index} className="text-center">
                <stat.icon className="w-8 h-8 text-indigo-200 mx-auto mb-2" />
                <p className="text-4xl font-bold text-white mb-1">{stat.value}</p>
                <p className="text-indigo-200 text-sm">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Why Choose Our Platform?
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Built with the latest technology to provide the most reliable verification service
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => (
              <div
                key={index}
                className="group p-6 rounded-xl border-2 border-gray-100 hover:border-indigo-200 hover:shadow-xl transition-all"
              >
                <div className={`w-14 h-14 ${feature.bgColor} rounded-lg flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                  <feature.icon className={`w-7 h-7 ${feature.color}`} />
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">
                  {feature.title}
                </h3>
                <p className="text-gray-600">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-24 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              How It Works
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Simple, fast, and efficient verification in four easy steps
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {howItWorks.map((item, index) => (
              <div key={index} className="relative">
                <div className="bg-white rounded-xl p-6 shadow-lg hover:shadow-xl transition-shadow">
                  <div className="w-12 h-12 bg-indigo-600 text-white rounded-full flex items-center justify-center text-xl font-bold mb-4">
                    {item.step}
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    {item.title}
                  </h3>
                  <p className="text-gray-600">
                    {item.description}
                  </p>
                </div>
                {index < howItWorks.length - 1 && (
                  <div className="hidden lg:block absolute top-1/2 -right-4 transform -translate-y-1/2">
                    <ArrowRight className="w-8 h-8 text-indigo-300" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 bg-indigo-600">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-4xl font-bold text-white mb-6">
            Ready to Get Started?
          </h2>
          <p className="text-xl text-indigo-100 mb-8">
            Join thousands of organizations using our platform for secure document verification
          </p>
          <button
          type='button'
            onClick={() => navigate('/register')}
            className="inline-flex items-center gap-2 px-8 py-4 bg-white text-indigo-600 rounded-lg hover:bg-gray-100 font-semibold text-lg transition-all hover:scale-105"
          >
            Create Free Account
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center mb-4">
                <Shield className="w-6 h-6 text-indigo-400" />
                <span className="ml-2 text-xl font-bold text-white">VettingSystem</span>
              </div>
              <p className="text-sm">
                AI-powered document verification and background checking platform.
              </p>
            </div>
            <div>
              <h3 className="text-white font-semibold mb-4">Product</h3>
              <ul className="space-y-2 text-sm">
                <li>
                  <button type="button" onClick={() => navigate('/register')} className="hover:text-white transition-colors">
                    Features
                  </button>
                </li>
                <li>
                  <button type="button" onClick={() => navigate('/register')} className="hover:text-white transition-colors">
                    Pricing
                  </button>
                </li>
                <li>
                  <button type="button" onClick={() => navigate('/register')} className="hover:text-white transition-colors">
                    API
                  </button>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="text-white font-semibold mb-4">Company</h3>
              <ul className="space-y-2 text-sm">
                <li>
                  <button type="button" onClick={() => navigate('/')} className="hover:text-white transition-colors">
                    About
                  </button>
                </li>
                <li>
                  <button type="button" onClick={() => navigate('/')} className="hover:text-white transition-colors">
                    Contact
                  </button>
                </li>
                <li>
                  <button type="button" onClick={() => navigate('/')} className="hover:text-white transition-colors">
                    Careers
                  </button>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="text-white font-semibold mb-4">Legal</h3>
              <ul className="space-y-2 text-sm">
                <li>
                  <button type="button" onClick={() => navigate('/')} className="hover:text-white transition-colors">
                    Privacy
                  </button>
                </li>
                <li>
                  <button type="button" onClick={() => navigate('/')} className="hover:text-white transition-colors">
                    Terms
                  </button>
                </li>
                <li>
                  <button type="button" onClick={() => navigate('/')} className="hover:text-white transition-colors">
                    Security
                  </button>
                </li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-800 mt-8 pt-8 text-center text-sm">
            <p>&copy; {new Date().getFullYear()} VettingSystem. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default HomePage;
