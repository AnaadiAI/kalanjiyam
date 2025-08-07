# Translation Service Documentation

## Overview

The Translation Service is a comprehensive system for translating OCR content and edited text in the Kalanjiyam proofing platform. It provides both individual page translation and batch translation capabilities, similar to the existing OCR system.

## Architecture

### Core Components

1. **Translation Model** (`kalanjiyam/models/proofing.py`)
   - `Translation` model for storing translation data
   - Links to specific page revisions
   - Supports multiple languages and engines

2. **Translation Engine** (`kalanjiyam/utils/translation_engine.py`)
   - Unified interface for different translation services
   - Support for Google Translate and OpenAI GPT
   - Text segmentation for optimal translation

3. **Translation Tasks** (`kalanjiyam/tasks/translation.py`)
   - Celery background tasks for translation
   - Batch translation for entire projects
   - Redis-based task tracking

4. **API Endpoints** (`kalanjiyam/views/proofing/page.py`)
   - Individual page translation API
   - Batch translation project routes

## Features

### Text Segmentation
- Automatically segments long text into manageable chunks
- Preserves paragraph structure and formatting
- Configurable maximum segment length (default: 1000 characters)

### Multiple Translation Engines
- **Google Translate**: Free, good for basic translations
- **OpenAI GPT**: Higher quality, requires API key
- Extensible architecture for adding more engines

### Language Support
- Sanskrit (sa) - Primary source language
- English (en) - Primary target language
- Hindi (hi), Telugu (te), Marathi (mr)
- French (fr), German (de), Spanish (es)
- Additional languages via engine capabilities

### Batch Processing
- Translate entire projects at once
- Progress tracking with Redis
- Resume capability if interrupted
- Background processing with Celery

## Database Schema

### Translation Table
```sql
CREATE TABLE proof_translations (
    id INTEGER PRIMARY KEY,
    page_id INTEGER NOT NULL,
    revision_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    source_language VARCHAR NOT NULL,
    target_language VARCHAR NOT NULL,
    translation_engine VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (page_id) REFERENCES proof_pages(id),
    FOREIGN KEY (revision_id) REFERENCES proof_revisions(id),
    FOREIGN KEY (author_id) REFERENCES users(id)
);
```

## Usage

### Individual Page Translation

#### API Endpoint
```
GET /api/translate/<project_slug>/<page_slug>/
```

#### Parameters
- `source_lang`: Source language code (default: 'sa')
- `target_lang`: Target language code (default: 'en')
- `engine`: Translation engine (default: 'google')
- `revision_id`: Specific revision ID (optional)

#### Example
```bash
curl "http://localhost:5000/api/translate/my-project/1/?source_lang=sa&target_lang=en&engine=google"
```

### Batch Translation

#### Web Interface
1. Navigate to project edit page
2. Click "Run batch translation"
3. Select source/target languages and engine
4. Start translation process
5. Monitor progress in real-time

#### Programmatic Usage
```python
from kalanjiyam.tasks.translation import run_translation_for_project

# Run batch translation
result = run_translation_for_project(
    app_env="development",
    project=project,
    source_lang="sa",
    target_lang="en",
    engine="google"
)

# Monitor progress
if result:
    progress = result.completed_count() / len(result.results)
    print(f"Progress: {progress:.1%}")
```

## Configuration

### Environment Variables
```bash
# Redis for task tracking
REDIS_URL=redis://localhost:6379/0

# OpenAI API (optional)
OPENAI_API_KEY=your_openai_api_key_here
```

### Dependencies
Add to `requirements.txt`:
```
googletrans==4.0.0rc1
openai>=1.0.0
```

## Installation

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Database Migration**
   ```bash
   alembic upgrade head
   ```

3. **Start Celery Worker**
   ```bash
   make celery
   ```

4. **Start Redis Server**
   ```bash
   redis-server
   ```

## API Reference

### Translation Engine Interface

```python
class TranslationEngine(ABC):
    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str, **kwargs) -> TranslationResponse:
        """Translate text from source to target language."""
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        pass
```

### Translation Response

```python
@dataclass
class TranslationResponse:
    translated_text: str
    source_language: str
    target_language: str
    engine: str
    metadata: Optional[Dict[str, Any]] = None
```

## Error Handling

### Common Issues

1. **Translation Engine Unavailable**
   - Check API keys for OpenAI
   - Verify internet connection for Google Translate
   - Check engine configuration

2. **Text Too Long**
   - Automatic segmentation handles this
   - Adjust `max_length` parameter if needed

3. **Language Not Supported**
   - Check engine's supported languages
   - Use fallback language if available

### Logging
Translation operations are logged with appropriate levels:
- `INFO`: Successful translations
- `WARNING`: Non-critical issues
- `ERROR`: Translation failures

## Performance Considerations

### Text Segmentation
- Optimal segment length: 1000 characters
- Preserves sentence boundaries
- Maintains paragraph structure

### Rate Limiting
- Google Translate: ~100 requests/minute
- OpenAI: Based on API tier
- Implement exponential backoff for retries

### Caching
- Translation results stored in database
- Avoid re-translating same content
- Consider Redis caching for frequent translations

## Future Enhancements

### Planned Features
1. **Translation Memory**
   - Cache common translations
   - Improve consistency across projects

2. **Quality Metrics**
   - Translation confidence scores
   - User feedback integration

3. **Advanced Engines**
   - Custom trained models
   - Domain-specific translations

4. **UI Improvements**
   - Side-by-side translation view
   - Translation editing interface
   - Translation comparison tools

### Integration Opportunities
1. **Dictionary Integration**
   - Link translations to dictionary entries
   - Provide word-level translations

2. **Collaborative Features**
   - Translation review workflow
   - Community translation contributions

3. **Export Options**
   - Export translations to various formats
   - Integration with external tools

## Troubleshooting

### Common Problems

1. **Translation Tasks Not Starting**
   - Check Celery worker status
   - Verify Redis connection
   - Check task queue configuration

2. **Poor Translation Quality**
   - Try different engines
   - Adjust text segmentation
   - Check source text quality

3. **Performance Issues**
   - Monitor Redis memory usage
   - Check Celery worker count
   - Optimize text segmentation

### Debug Mode
Enable debug logging for translation operations:
```python
import logging
logging.getLogger('kalanjiyam.utils.translation_engine').setLevel(logging.DEBUG)
```

## Contributing

### Adding New Translation Engines

1. Implement the `TranslationEngine` interface
2. Add engine to `TranslationEngineFactory`
3. Update tests and documentation
4. Add configuration options

### Testing
Run translation tests:
```bash
pytest test/kalanjiyam/utils/test_translation_engine.py -v
```

## License

This translation service is part of the Kalanjiyam project and follows the same license terms. 