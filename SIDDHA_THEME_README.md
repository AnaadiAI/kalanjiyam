# Kalanjiyam - Siddha Knowledge Systems Theme

## Overview

Kalanjiyam has been customized for the Siddha ecosystem with a focus on preserving and sharing ancient Siddha wisdom. The platform is dedicated to collaborative proofing and digital preservation of Siddha texts.

## Theme Changes

### Visual Design
- **Logo**: Created a new Siddha-themed logo featuring Murugan's peacock (mayil) and vel (spear)
- **Colors**: Enhanced the peacock theme with Murugan-inspired colors (violet, teal, gold)
- **Favicon**: New SVG favicon representing the Siddha theme

### Content Updates
- **Homepage**: Updated to focus on Siddha wisdom and preservation
- **Navigation**: Simplified to focus on proofing functionality
- **About Pages**: Updated mission and content to reflect Siddha focus
- **Meta Tags**: Updated descriptions and keywords for Siddha content

### Key Features
- **Proofing Focus**: Platform dedicated to collaborative text proofing
- **Siddha Content**: Emphasis on traditional medicine, alchemy, yoga, and spiritual practices
- **Community-Driven**: Volunteer-based preservation efforts
- **Digital Preservation**: Modern tools for traditional knowledge

## Files Modified

### Templates
- `kalanjiyam/templates/index.html` - Updated homepage content
- `kalanjiyam/templates/base.html` - Updated meta descriptions
- `kalanjiyam/templates/include/header.html` - Simplified navigation
- `kalanjiyam/templates/about/index.html` - Updated about content
- `kalanjiyam/templates/about/mission.html` - Updated mission statement

### Static Assets
- `kalanjiyam/static/images/siddha-logo.svg` - New Siddha logo
- `kalanjiyam/static/favicon.svg` - New favicon
- `kalanjiyam/static/css/style.css` - Enhanced color scheme

### Configuration
- `config.py` - Added URL prefix configuration
- `kalanjiyam/__init__.py` - Updated blueprint registration for URL prefixing

## Deployment

### URL Structure
The application is configured to be hosted at `siddhasagaram.in/kalanjiyam` using the `APPLICATION_URL_PREFIX` environment variable.

### Environment Variables
```bash
APPLICATION_URL_PREFIX=/kalanjiyam
```

### Nginx Configuration
See `deploy/siddhasagaram-config.md` for complete deployment instructions.

## Siddha Theme Elements

### Murugan/Mayil Theme
- **Peacock Colors**: Teal, cyan, violet gradient representing Murugan's peacock
- **Gold Accents**: Amber/gold colors representing peacock feathers
- **Spiritual Elements**: Integration of traditional Siddha symbolism

### Content Focus
- **Traditional Medicine**: Siddha medical texts and practices
- **Alchemy**: Ancient alchemical knowledge
- **Yoga**: Spiritual and physical practices
- **Text Preservation**: Collaborative proofing of manuscripts

## Community Involvement

The platform encourages community participation in:
- Text proofing and verification
- Knowledge sharing and translation
- Preservation of traditional practices
- Research and documentation

## Future Enhancements

Potential areas for development:
- Siddha-specific dictionary integration
- Traditional medicine database
- Community forums for practitioners
- Multilingual support for regional languages
- Integration with existing Siddha repositories

## Contributing

To contribute to the Siddha theme or functionality:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Contact

For questions about the Siddha theme or deployment:
- Check the deployment guide in `deploy/siddhasagaram-config.md`
- Review the configuration options in `config.py`
- Contact the development team through the platform's contact form 