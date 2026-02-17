# backend/apps/interviews/flag_generator.py

class InterrogationFlagGenerator:
    """Generate structured interrogation flags from vetting results"""

    @staticmethod
    def generate_flags_from_vetting(application):
        """Create flags based on document vetting results"""

        flags = []

        # 1. Consistency Flags
        consistency_flags = InterrogationFlagGenerator._check_consistency(application)
        flags.extend(consistency_flags)

        # 2. Authenticity Flags
        authenticity_flags = InterrogationFlagGenerator._check_authenticity(application)
        flags.extend(authenticity_flags)

        # 3. Timeline Flags
        timeline_flags = InterrogationFlagGenerator._check_timelines(application)
        flags.extend(timeline_flags)

        # 4. Missing Data Flags
        missing_flags = InterrogationFlagGenerator._check_missing_data(application)
        flags.extend(missing_flags)

        return flags

    @staticmethod
    def _check_consistency(application):
        """Check for data inconsistencies across documents"""
        flags = []

        # Extract data from all documents
        documents_data = {}
        for doc in application.documents.all():
            verification = doc.verification_results.first()
            if verification and verification.details:
                documents_data[doc.document_type] = verification.details

        # Check name consistency
        names = set()
        for doc_type, data in documents_data.items():
            if 'name' in data:
                names.add(data['name'].lower().strip())

        if len(names) > 1:
            flags.append({
                'flag_type': 'consistency_mismatch',
                'severity': 'high',
                'context': f"Different names found across documents: {', '.join(names)}",
                'data_point': {'names_found': list(names)},
                'source_document_ids': [doc.id for doc in application.documents.all()]
            })

        # Check date consistency
        if 'resume' in documents_data and 'employment_letter' in documents_data:
            resume_start = documents_data['resume'].get('employment_start_date')
            letter_start = documents_data['employment_letter'].get('start_date')

            if resume_start and letter_start and resume_start != letter_start:
                flags.append({
                    'flag_type': 'consistency_mismatch',
                    'severity': 'medium',
                    'context': f"Employment start date mismatch: Resume says {resume_start}, Letter says {letter_start}",
                    'data_point': {
                        'resume_date': resume_start,
                        'letter_date': letter_start
                    },
                    'source_document_ids': [
                        application.documents.get(document_type='resume').id,
                        application.documents.get(document_type='employment_letter').id
                    ]
                })

        return flags

    @staticmethod
    def _check_authenticity(application):
        """Check for low authenticity scores"""
        flags = []

        for doc in application.documents.all():
            verification = doc.verification_results.first()
            if verification and verification.authenticity_score < 70:
                flags.append({
                    'flag_type': 'authenticity_concern',
                    'severity': 'high' if verification.authenticity_score < 50 else 'medium',
                    'context': f"{doc.document_type} has low authenticity score ({verification.authenticity_score:.1f}%)",
                    'data_point': {
                        'document_type': doc.document_type,
                        'authenticity_score': verification.authenticity_score,
                        'concerns': verification.details.get('concerns', [])
                    },
                    'source_document_ids': [doc.id]
                })

        return flags

    @staticmethod
    def _check_timelines(application):
        """Check for timeline gaps or inconsistencies"""
        flags = []

        # Extract all dates from documents
        dates = []
        for doc in application.documents.all():
            verification = doc.verification_results.first()
            if verification and verification.details:
                for key, value in verification.details.items():
                    if 'date' in key.lower() and value:
                        dates.append({
                            'document': doc.document_type,
                            'field': key,
                            'date': value
                        })

        # Check for large gaps (>1 year unexplained)
        # Implementation depends on your business logic

        return flags

    @staticmethod
    def _check_missing_data(application):
        """Check for missing critical information"""
        flags = []

        required_docs = ['id_card', 'certificate', 'employment_letter']
        submitted_types = [doc.document_type for doc in application.documents.all()]

        for required in required_docs:
            if required not in submitted_types:
                flags.append({
                    'flag_type': 'missing_data',
                    'severity': 'high',
                    'context': f"Required document '{required}' not submitted",
                    'data_point': {'missing_document': required},
                    'source_document_ids': []
                })

        return flags