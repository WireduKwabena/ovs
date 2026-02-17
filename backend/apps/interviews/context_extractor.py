# backend/apps/interviews/context_extractor.py

class ApplicantContextExtractor:
    """Extract relevant context from documents for interview"""

    @staticmethod
    def extract_from_application(application):
        """Build comprehensive applicant context"""

        context = {
            'basic_info': ApplicantContextExtractor._extract_basic_info(application),
            'education': ApplicantContextExtractor._extract_education(application),
            'experience': ApplicantContextExtractor._extract_experience(application),
            'skills': ApplicantContextExtractor._extract_skills(application),
            'documents_submitted': ApplicantContextExtractor._list_documents(application),
            'inconsistencies_from_docs': ApplicantContextExtractor._find_doc_inconsistencies(application)
        }

        return context

    @staticmethod
    def _extract_basic_info(application):
        """Extract basic applicant information"""
        return {
            'name': application.applicant.full_name,
            'email': application.applicant.email,
            'phone': application.applicant.phone_number,
            'dob': str(application.applicant.date_of_birth) if hasattr(application.applicant,
                                                                       'date_of_birth') else None,
            'application_type': application.application_type
        }

    @staticmethod
    def _extract_education(application):
        """Extract education information from documents"""
        education = []

        cert_docs = application.documents.filter(
            document_type__in=['certificate', 'diploma', 'transcript']
        )

        for doc in cert_docs:
            verification = doc.verification_results.first()
            if verification and verification.details:
                education.append({
                    'document': doc.document_type,
                    'data': verification.details
                })

        return education

    @staticmethod
    def _extract_experience(application):
        """Extract work experience from documents"""
        experience = []

        work_docs = application.documents.filter(
            document_type__in=['employment_letter', 'reference_letter', 'resume']
        )

        for doc in work_docs:
            verification = doc.verification_results.first()
            if verification:
                experience.append({
                    'document': doc.document_type,
                    'text_extract': verification.ocr_text[:500],  # First 500 chars
                    'data': verification.details
                })

        return experience

    @staticmethod
    def _extract_skills(application):
        """Extract mentioned skills from all documents"""
        import re

        all_text = ''
        for doc in application.documents.all():
            verification = doc.verification_results.first()
            if verification:
                all_text += verification.ocr_text + ' '

        # Common skill keywords
        skill_keywords = [
            'python', 'javascript', 'java', 'management', 'leadership',
            'communication', 'analysis', 'project management', 'sql',
            'excel', 'powerpoint', 'research', 'design', 'marketing'
        ]

        found_skills = []
        text_lower = all_text.lower()

        for skill in skill_keywords:
            if skill in text_lower:
                found_skills.append(skill)

        return found_skills

    @staticmethod
    def _list_documents(application):
        """List all submitted documents"""
        return [
            {
                'type': doc.document_type,
                'authenticity_score': doc.verification_results.first().authenticity_score if doc.verification_results.exists() else None
            }
            for doc in application.documents.all()
        ]

    @staticmethod
    def _find_doc_inconsistencies(application):
        """Find inconsistencies across documents"""
        inconsistencies = []

        # Check for name variations
        names_found = set()
        for doc in application.documents.all():
            verification = doc.verification_results.first()
            if verification and verification.details:
                name = verification.details.get('name') or verification.details.get('recipient_name')
                if name:
                    names_found.add(name.lower().strip())

        if len(names_found) > 1:
            inconsistencies.append({
                'type': 'name_variation',
                'details': f"Different names found: {', '.join(names_found)}"
            })

        # Check for date inconsistencies
        dates_found = []
        for doc in application.documents.all():
            verification = doc.verification_results.first()
            if verification and verification.details:
                if 'date_issued' in verification.details:
                    dates_found.append({
                        'document': doc.document_type,
                        'date': verification.details['date_issued']
                    })

        # Add more consistency checks as needed

        return inconsistencies