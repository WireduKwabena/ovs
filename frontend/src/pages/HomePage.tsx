import React from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import "./HomePage.css";

type FeatureCard = {
  icon: string;
  title: string;
  description: string;
};

type ProcessStep = {
  title: string;
  description: string;
};

type Benefit = {
  icon: string;
  title: string;
  description: string;
};

const featureCards: FeatureCard[] = [
  {
    icon: "📄",
    title: "Automated Resume Parsing",
    description:
      "Extract and analyze resume data in seconds. Our AI identifies skills, experience, education, and red flags automatically.",
  },
  {
    icon: "🔍",
    title: "Background Verification",
    description:
      "Cross-reference employment history, education credentials, and professional certifications across multiple databases instantly.",
  },
  {
    icon: "🎯",
    title: "Skill Assessment",
    description:
      "AI-powered technical and soft skills evaluation through adaptive testing and behavioral analysis.",
  },
  {
    icon: "🤖",
    title: "AI Video Interviews",
    description:
      "Conduct and analyze video interviews automatically. Evaluate communication skills, confidence, and cultural fit.",
  },
  {
    icon: "⚠️",
    title: "Fraud Detection",
    description:
      "Advanced algorithms detect inconsistencies, fake credentials, and suspicious patterns in applications.",
  },
  {
    icon: "📊",
    title: "Smart Analytics",
    description:
      "Get detailed reports with candidate rankings, comparison charts, and hiring recommendations powered by data.",
  },
];

const processSteps: ProcessStep[] = [
  {
    title: "Upload Candidates",
    description: "Import resumes via bulk upload, API integration, or direct application links",
  },
  {
    title: "AI Analysis",
    description:
      "Our AI instantly parses, verifies, and scores each candidate against your criteria",
  },
  {
    title: "Deep Vetting",
    description:
      "Automated background checks, skill tests, and credential verification run simultaneously",
  },
  {
    title: "Get Results",
    description:
      "Review comprehensive reports with recommendations and make confident hiring decisions",
  },
];

const benefits: Benefit[] = [
  {
    icon: "💰",
    title: "Reduce Hiring Costs by 70%",
    description:
      "Eliminate manual screening hours and reduce bad hires with AI-powered accuracy",
  },
  {
    icon: "🎯",
    title: "Increase Quality of Hire",
    description:
      "Data-driven insights ensure you only interview the best-matched candidates",
  },
  {
    icon: "⚖️",
    title: "Eliminate Bias",
    description:
      "Objective AI evaluation ensures fair assessment based purely on qualifications",
  },
  {
    icon: "🔒",
    title: "Enterprise-Grade Security",
    description:
      "Bank-level encryption and compliance with GDPR, SOC 2, and industry standards",
  },
  {
    icon: "📈",
    title: "Scale Effortlessly",
    description:
      "Process thousands of candidates simultaneously without additional resources",
  },
];

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const {
    isAuthenticated,
    userType,
    activeOrganizationId,
    canManageActiveOrganizationGovernance,
  } = useAuth();

  const startOrganizationPath = "/organization/setup?next=%2Forganization%2Fdashboard";

  const handleGetStarted = () => {
    if (!isAuthenticated) {
      navigate("/organization/get-started?next=%2Fsubscribe");
      return;
    }

    if (userType === "applicant") {
      navigate("/candidate/access");
      return;
    }

    if (!activeOrganizationId) {
      navigate(startOrganizationPath);
      return;
    }

    if (canManageActiveOrganizationGovernance) {
      navigate("/organization/dashboard");
      return;
    }

    navigate("/workspace");
  };

  const handleInternalLogin = () => navigate("/login");
  const handleCandidateAccess = () => navigate("/candidate/access");

  return (
    <div className="vetai-home">
      <div className="vetai-hero">
        <nav className="vetai-nav">
          <div className="vetai-logo">
            <div className="vetai-logo-icon">🤖</div>
            VetAI
          </div>
          <div className="vetai-nav-links">
            <a href="#features">Features</a>
            <a href="#process">How It Works</a>
            <a href="#pricing">Pricing</a>
            <a href="#demo" className="vetai-btn vetai-btn-primary">
              Get Demo
            </a>
          </div>
        </nav>

        <div className="vetai-hero-content">
          <div className="vetai-hero-text">
            <h1>
              <span className="vetai-gradient-text">AI-Powered</span>
              <br />
              Candidate Vetting
              <br />
              in Minutes
            </h1>
            <p>
              Transform your hiring process with intelligent automation. Screen, verify, and
              evaluate candidates 10x faster with our advanced AI vetting system.
            </p>

            <div className="vetai-hero-buttons">
              <button type="button" className="vetai-btn vetai-btn-primary" onClick={handleGetStarted}>
                Start Free Trial
              </button>
              <button type="button" className="vetai-btn vetai-btn-secondary" onClick={handleInternalLogin}>
                Watch Demo
              </button>
              <button type="button" className="vetai-btn vetai-btn-secondary" onClick={handleCandidateAccess}>
                Candidate Access
              </button>
            </div>

            <div className="vetai-stats">
              <div className="vetai-stat-item">
                <div className="vetai-stat-number">95%</div>
                <div className="vetai-stat-label">Accuracy Rate</div>
              </div>
              <div className="vetai-stat-item">
                <div className="vetai-stat-number">10x</div>
                <div className="vetai-stat-label">Faster Screening</div>
              </div>
              <div className="vetai-stat-item">
                <div className="vetai-stat-number">50K+</div>
                <div className="vetai-stat-label">Candidates Vetted</div>
              </div>
            </div>
          </div>

          <div className="vetai-hero-visual">
            <div className="vetai-floating-card vetai-card-1">
              <div className="vetai-card-icon">✓</div>
              <div className="vetai-card-title">Resume Verified</div>
              <div className="vetai-card-subtitle">99.2% Match Score</div>
            </div>
            <div className="vetai-floating-card vetai-card-2">
              <div className="vetai-card-icon">🎓</div>
              <div className="vetai-card-title">Credentials Check</div>
              <div className="vetai-card-subtitle">All Documents Valid</div>
            </div>
            <div className="vetai-floating-card vetai-card-3">
              <div className="vetai-card-icon">⚡</div>
              <div className="vetai-card-title">Skills Assessment</div>
              <div className="vetai-card-subtitle">Expert Level Confirmed</div>
            </div>
          </div>
        </div>
      </div>

      <section className="vetai-features" id="features">
        <div className="vetai-features-container">
          <div className="vetai-section-header">
            <div className="vetai-section-label">FEATURES</div>
            <h2 className="vetai-section-title">Everything You Need to Vet Smarter</h2>
            <p className="vetai-section-subtitle">
              Powered by advanced AI and machine learning, our platform automates every step of
              candidate verification
            </p>
          </div>

          <div className="vetai-features-grid">
            {featureCards.map((feature) => (
              <div key={feature.title} className="vetai-feature-card">
                <div className="vetai-feature-icon">{feature.icon}</div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="vetai-process" id="process">
        <div className="vetai-process-container">
          <div className="vetai-section-header">
            <div className="vetai-section-label vetai-section-label-process">HOW IT WORKS</div>
            <h2 className="vetai-section-title vetai-section-title-process">Vetting Made Simple</h2>
            <p className="vetai-section-subtitle vetai-section-subtitle-process">
              Four easy steps from candidate submission to verified hire
            </p>
          </div>

          <div className="vetai-process-steps">
            {processSteps.map((step, index) => (
              <div key={step.title} className="vetai-process-step">
                <div className="vetai-step-number">{index + 1}</div>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="vetai-benefits" id="pricing">
        <div className="vetai-benefits-container">
          <div className="vetai-benefits-visual">
            <div className="vetai-benefits-visual-content">
              <div className="vetai-benefits-rocket">🚀</div>
              <h3>10x Faster Hiring</h3>
              <p>Average time to vet: 3 minutes</p>
            </div>
          </div>

          <div className="vetai-benefits-list">
            {benefits.map((benefit) => (
              <div key={benefit.title} className="vetai-benefit-item">
                <div className="vetai-benefit-icon">{benefit.icon}</div>
                <div className="vetai-benefit-content">
                  <h3>{benefit.title}</h3>
                  <p>{benefit.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="vetai-cta" id="demo">
        <div className="vetai-cta-content">
          <h2>Ready to Transform Your Hiring?</h2>
          <p>Join 2,000+ companies using VetAI to make smarter hiring decisions</p>

          <div className="vetai-cta-buttons">
            <button type="button" className="vetai-btn vetai-btn-primary" onClick={handleGetStarted}>
              Start Free 14-Day Trial
            </button>
            <button type="button" className="vetai-btn vetai-btn-secondary" onClick={handleInternalLogin}>
              Schedule Demo
            </button>
          </div>

          <div className="vetai-trust-badges">
            <div className="vetai-badge">✓ No credit card required</div>
            <div className="vetai-badge">✓ Setup in 5 minutes</div>
            <div className="vetai-badge">✓ Cancel anytime</div>
          </div>
        </div>
      </section>

      <footer className="vetai-footer">
        <div className="vetai-footer-content">
          <div className="vetai-footer-brand">
            <div className="vetai-logo">
              <div className="vetai-logo-icon">🤖</div>
              VetAI
            </div>
            <p>
              AI-powered candidate vetting that helps you hire better, faster, and smarter.
            </p>
            <div className="vetai-social-links">
              <a href="#" className="vetai-social-link" aria-label="X">
                𝕏
              </a>
              <a href="#" className="vetai-social-link" aria-label="LinkedIn">
                in
              </a>
              <a href="#" className="vetai-social-link" aria-label="Facebook">
                f
              </a>
            </div>
          </div>

          <div className="vetai-footer-section">
            <h4>Product</h4>
            <a href="#features">Features</a>
            <a href="#pricing">Pricing</a>
            <a href="#">Integrations</a>
            <a href="#">API Docs</a>
          </div>

          <div className="vetai-footer-section">
            <h4>Resources</h4>
            <a href="#">Blog</a>
            <a href="#">Case Studies</a>
            <a href="#">Help Center</a>
            <a href="#">Webinars</a>
          </div>

          <div className="vetai-footer-section">
            <h4>Company</h4>
            <a href="#">About Us</a>
            <a href="#">Careers</a>
            <a href="#">Contact</a>
            <a href="#">Privacy Policy</a>
          </div>
        </div>

        <div className="vetai-footer-bottom">
          <p>&copy; {new Date().getFullYear()} VetAI. All rights reserved. | Powered by Advanced AI Technology</p>
        </div>
      </footer>
    </div>
  );
};

export default HomePage;


