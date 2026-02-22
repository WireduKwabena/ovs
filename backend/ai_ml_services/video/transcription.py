"""
Video Transcription Service
============================

Speech-to-text transcription using OpenAI Whisper.

Academic Note:
--------------
Whisper is a state-of-the-art speech recognition model from OpenAI:
- Trained on 680,000 hours of multilingual data
- Robust to accents, background noise, technical language
- Multiple model sizes: tiny, base, small, medium, large
- Open-source and runs locally (no API costs)

Model Selection Guide:
- tiny: Fast, lower accuracy (~32x realtime on CPU)
- base: Good balance (~16x realtime on CPU)
- small: Better accuracy (~6x realtime on CPU)
- medium: High accuracy (~2x realtime on CPU)
- large: Best accuracy (~1x realtime on CPU, needs GPU)

For academic project: Use 'base' model (good speed/accuracy trade-off)
For production: Use 'small' or 'medium' model

Reference:
Radford, A., et al. (2022). "Robust Speech Recognition via Large-Scale Weak Supervision"
https://arxiv.org/abs/2212.04356
"""

import whisper
import torch
import numpy as np
from pathlib import Path
from typing import Dict, Optional
import logging
import time
import asyncio
import tempfile
import base64
import binascii

try:
    from moviepy.editor import VideoFileClip
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    VideoFileClip = None

logger = logging.getLogger(__name__)


class TranscriptionService:
    """
    Automatic speech recognition using Whisper.
    
    Features:
    - Multiple language support
    - Word-level timestamps
    - Confidence scores
    - Audio enhancement preprocessing
    - GPU acceleration
    """
    
    def __init__(
        self,
        model_size: str = "base",
        device: Optional[str] = None,
        language: Optional[str] = "en"
    ):
        """
        Initialize transcription service.
        
        Args:
            model_size: Whisper model size (tiny/base/small/medium/large)
            device: Device to run on ('cuda', 'cpu', or None for auto-detect)
            language: Expected language code (None for auto-detection)
        """
        self.model_size = model_size
        self.language = language
        
        # Device setup
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        logger.info(f"Initializing Whisper model '{model_size}' on {self.device}")
        
        # Load model
        self.model = whisper.load_model(model_size, device=self.device)
        
        logger.info("Whisper model loaded successfully")
    
    def extract_audio_from_video(
        self,
        video_path: str,
        output_path: Optional[str] = None
    ) -> str:
        """
        Extract audio track from video file.
        
        Args:
            video_path: Path to video file
            output_path: Optional output path for audio file
        
        Returns:
            Path to extracted audio file
        """
        video_path = Path(video_path)
        
        if output_path is None:
            # Create temp file
            temp_dir = Path(tempfile.gettempdir())
            output_path = temp_dir / f"{video_path.stem}_audio.wav"
        
        logger.info(f"Extracting audio from {video_path}")
        
        try:
            if VideoFileClip is None:
                raise RuntimeError(
                    "moviepy is required to extract audio from video files. "
                    "Install it with `pip install moviepy`."
                )

            # Load video
            video = VideoFileClip(str(video_path))
            
            # Extract audio
            audio = video.audio
            
            if audio is None:
                raise ValueError(f"No audio track found in {video_path}")
            
            # Write audio file
            audio.write_audiofile(
                str(output_path),
                fps=16000,  # Whisper expects 16kHz
                nbytes=2,
                codec='pcm_s16le',
                logger=None  # Suppress moviepy logs
            )
            
            # Close clips
            video.close()
            audio.close()
            
            logger.info(f"Audio extracted to {output_path}")
            return str(output_path)
        
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            raise
    
    def transcribe(
        self,
        audio_path: str,
        word_timestamps: bool = True,
        task: str = "transcribe"
    ) -> Dict:
        """
        Transcribe audio file.
        
        Args:
            audio_path: Path to audio or video file
            word_timestamps: Include word-level timestamps
            task: 'transcribe' or 'translate' (to English)
        
        Returns:
            Transcription results dictionary
        """
        audio_path = Path(audio_path)
        
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        logger.info(f"Transcribing {audio_path}")
        start_time = time.time()
        
        try:
            # Transcribe
            result = self.model.transcribe(
                str(audio_path),
                language=self.language,
                task=task,
                word_timestamps=word_timestamps,
                verbose=False
            )
            
            processing_time = time.time() - start_time
            
            # Extract information
            transcript = result['text'].strip()
            language = result.get('language', 'unknown')
            
            # Word-level details
            words = []
            if word_timestamps and 'segments' in result:
                for segment in result['segments']:
                    if 'words' in segment:
                        for word_info in segment['words']:
                            words.append({
                                'word': word_info['word'].strip(),
                                'start': word_info['start'],
                                'end': word_info['end'],
                                'confidence': word_info.get('probability', 1.0)
                            })
            
            # Calculate average confidence
            if words:
                avg_confidence = np.mean([w['confidence'] for w in words])
            else:
                avg_confidence = 1.0  # Default if no word-level data
            
            # Duration
            duration = 0
            if words:
                duration = words[-1]['end']
            elif 'segments' in result and result['segments']:
                duration = result['segments'][-1]['end']
            
            transcription_result = {
                'transcript': transcript,
                'language': language,
                'confidence': float(avg_confidence),
                'duration_seconds': float(duration),
                'processing_time_seconds': processing_time,
                'words': words,
                'word_count': len(transcript.split()),
                'model_used': self.model_size
            }
            
            logger.info(
                f"Transcription complete: {len(transcript)} chars, "
                f"{transcription_result['word_count']} words, "
                f"confidence: {avg_confidence:.2f}, "
                f"time: {processing_time:.1f}s"
            )
            
            return transcription_result
        
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
    
    def transcribe_video(
        self,
        video_path: str,
        cleanup_audio: bool = True
    ) -> Dict:
        """
        Transcribe video file (extracts audio first).
        
        Args:
            video_path: Path to video file
            cleanup_audio: Delete extracted audio after transcription
        
        Returns:
            Transcription results
        """
        # Extract audio
        audio_path = self.extract_audio_from_video(video_path)
        
        try:
            # Transcribe
            result = self.transcribe(audio_path)
            
            # Add video info
            result['source_video'] = str(video_path)
            result['extracted_audio'] = audio_path
            
            return result
        
        finally:
            # Cleanup
            if cleanup_audio and Path(audio_path).exists():
                Path(audio_path).unlink()
                logger.info(f"Cleaned up temporary audio file: {audio_path}")
    
    def get_speaking_rate(self, transcription: Dict) -> float:
        """
        Calculate speaking rate (words per minute).
        
        Args:
            transcription: Transcription result dictionary
        
        Returns:
            Words per minute
        """
        if transcription['duration_seconds'] > 0:
            wpm = (transcription['word_count'] / transcription['duration_seconds']) * 60
            return round(wpm, 1)
        return 0.0
    
    def detect_filler_words(self, transcription: Dict) -> Dict:
        """
        Detect filler words (um, uh, like, you know, etc.).
        
        Args:
            transcription: Transcription result dictionary
        
        Returns:
            Filler word statistics
        """
        filler_words = {
            'um', 'uh', 'umm', 'uhh', 'like', 'you know', 'so',
            'basically', 'actually', 'literally', 'right', 'okay'
        }
        
        transcript_lower = transcription['transcript'].lower()
        words = transcript_lower.split()
        
        filler_count = {}
        total_fillers = 0
        
        for filler in filler_words:
            count = transcript_lower.count(filler)
            if count > 0:
                filler_count[filler] = count
                total_fillers += count
        
        total_words = len(words)
        filler_percentage = (total_fillers / total_words * 100) if total_words > 0 else 0
        
        return {
            'total_filler_words': total_fillers,
            'filler_percentage': round(filler_percentage, 2),
            'filler_breakdown': filler_count,
            'speaking_fluency_score': max(0, 100 - filler_percentage * 2)  # Penalty for fillers
        }


# Django integration function
def transcribe_interview_response(response_id: int) -> Dict:
    """
    Transcribe interview response for Django model.
    
    Usage in Celery task:
    ```python
    from ai_ml_services.video.transcription import transcribe_interview_response
    
    result = transcribe_interview_response(response_id=123)
    ```
    """
    from apps.interviews.models import InterviewResponse
    from django.conf import settings
    
    # Get response
    response = InterviewResponse.objects.get(id=response_id)
    
    # Initialize service
    model_size = getattr(settings, 'WHISPER_MODEL_SIZE', 'base')
    service = TranscriptionService(model_size=model_size)
    
    # Transcribe
    if response.video_file:
        result = service.transcribe_video(response.video_file.path)
    elif response.audio_file:
        result = service.transcribe(response.audio_file.path)
    else:
        raise ValueError(f"Response {response_id} has no video or audio file")
    
    # Calculate additional metrics
    speaking_rate = service.get_speaking_rate(result)
    filler_analysis = service.detect_filler_words(result)
    
    # Update response
    response.transcript = result['transcript']
    response.transcript_confidence = result['confidence']
    response.response_duration_seconds = int(result['duration_seconds'])
    response.save()
    
    # Combine results
    full_result = {
        **result,
        'speaking_rate_wpm': speaking_rate,
        'filler_analysis': filler_analysis
    }
    
    logger.info(f"Transcription complete for response {response_id}")
    
    return full_result


async def transcribe_audio(
    audio_bytes: bytes | str,
    model_size: str = "base",
    language: Optional[str] = "en",
) -> str:
    """
    Transcribe raw audio bytes and return plain text transcript.
    """
    if not audio_bytes:
        return ""

    if isinstance(audio_bytes, str):
        try:
            audio_bytes = base64.b64decode(audio_bytes, validate=True)
        except (binascii.Error, ValueError):
            audio_bytes = audio_bytes.encode("utf-8")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
        temp_audio.write(audio_bytes)
        temp_path = Path(temp_audio.name)

    try:
        service = TranscriptionService(model_size=model_size, language=language)
        result = await asyncio.to_thread(service.transcribe, str(temp_path))
        return result.get("transcript", "")
    finally:
        temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    # Test transcription
    service = TranscriptionService(model_size="base")
    
    # Test on sample file
    result = service.transcribe_video("test_video.mp4")
    
    print(f"Transcript: {result['transcript']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Duration: {result['duration_seconds']}s")
    print(f"Word count: {result['word_count']}")
    
    # Speaking metrics
    wpm = service.get_speaking_rate(result)
    print(f"Speaking rate: {wpm} words/minute")
    
    fillers = service.detect_filler_words(result)
    print(f"Filler words: {fillers['total_filler_words']} ({fillers['filler_percentage']}%)")
