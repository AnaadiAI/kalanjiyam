/* global Alpine, $, OpenSeadragon, Sanscript, IMAGE_URL */
/* Transcription and proofreading interface. */

import { $ } from './core.ts';

const CONFIG_KEY = 'proofing-editor';

const LAYOUT_SIDE_BY_SIDE = 'side-by-side';
const LAYOUT_TOP_AND_BOTTOM = 'top-and-bottom';
const ALL_LAYOUTS = [LAYOUT_SIDE_BY_SIDE, LAYOUT_TOP_AND_BOTTOM];

const CLASSES_SIDE_BY_SIDE = 'flex flex-col-reverse md:flex-row h-[90vh]';
const CLASSES_TOP_AND_BOTTOM = 'flex flex-col-reverse h-[90vh]';

/* Initialize our image viewer. */
function initializeImageViewer(imageURL) {
  return OpenSeadragon({
    id: 'osd-image',
    tileSources: {
      type: 'image',
      url: imageURL,
      buildPyramid: false,
    },

    // Buttons
    showZoomControl: false,
    showHomeControl: false,
    showRotationControl: true,
    showFullPageControl: false,
    // Zoom buttons are defined in the `Editor` component below.
    rotateLeftButton: 'osd-rotate-left',
    rotateRightButton: 'osd-rotate-right',

    // Animations
    gestureSettingsMouse: {
      flickEnabled: true,
    },
    animationTime: 0.5,

    // The zoom multiplier to use when using the zoom in/out buttons.
    zoomPerClick: 1.1,
    // Max zoom level
    maxZoomPixelRatio: 2.5,
  });
}

export default () => ({
  // Settings
  textZoom: 1,
  imageZoom: null,
  layout: 'side-by-side',
  // [transliteration] the source script
  fromScript: 'hk',
  // [transliteration] the destination script
  toScript: 'devanagari',

  // Content
  content: '',

  // OCR settings
  selectedEngine: 'google',
  selectedLanguage: 'sa',

  // Internal-only
  layoutClasses: CLASSES_SIDE_BY_SIDE,
  isRunningOCR: false,
  hasUnsavedChanges: false,
  imageViewer: null,

  // OCR Engine configurations
  ocrEngines: {
    google: {
      name: 'Google OCR',
      languages: [
        { value: 'sa', text: 'Sanskrit (sa)' },
        { value: 'en', text: 'English (en)' },
        { value: 'hi', text: 'Hindi (hi)' },
        { value: 'te', text: 'Telugu (te)' },
        { value: 'mr', text: 'Marathi (mr)' },
        { value: 'bn', text: 'Bengali (bn)' },
        { value: 'gu', text: 'Gujarati (gu)' },
        { value: 'kn', text: 'Kannada (kn)' },
        { value: 'ml', text: 'Malayalam (ml)' },
        { value: 'ta', text: 'Tamil (ta)' },
        { value: 'pa', text: 'Punjabi (pa)' },
        { value: 'or', text: 'Odia (or)' },
        { value: 'ur', text: 'Urdu (ur)' }
      ],
      supportsBilingual: false
    },
    tesseract: {
      name: 'Tesseract OCR',
      languages: [
        { value: 'san', text: 'Sanskrit (san)' },
        { value: 'eng', text: 'English (eng)' },
        { value: 'hin', text: 'Hindi (hin)' },
        { value: 'tel', text: 'Telugu (tel)' },
        { value: 'mar', text: 'Marathi (mar)' },
        { value: 'ben', text: 'Bengali (ben)' },
        { value: 'guj', text: 'Gujarati (guj)' },
        { value: 'kan', text: 'Kannada (kan)' },
        { value: 'mal', text: 'Malayalam (mal)' },
        { value: 'tam', text: 'Tamil (tam)' },
        { value: 'pan', text: 'Punjabi (pan)' },
        { value: 'ori', text: 'Odia (ori)' },
        { value: 'urd', text: 'Urdu (urd)' }
      ],
      supportsBilingual: true,
      bilingualSeparator: '+'
    },
    surya: {
      name: 'Surya OCR',
      languages: [
        { value: 'sa', text: 'Sanskrit (sa)' },
        { value: 'hi', text: 'Hindi (hi)' },
        { value: 'te', text: 'Telugu (te)' },
        { value: 'mr', text: 'Marathi (mr)' },
        { value: 'bn', text: 'Bengali (bn)' },
        { value: 'gu', text: 'Gujarati (gu)' },
        { value: 'kn', text: 'Kannada (kn)' },
        { value: 'ml', text: 'Malayalam (ml)' },
        { value: 'ta', text: 'Tamil (ta)' },
        { value: 'pa', text: 'Punjabi (pa)' },
        { value: 'or', text: 'Odia (or)' },
        { value: 'ur', text: 'Urdu (ur)' },
        { value: 'en', text: 'English (en)' },
        { value: 'ar', text: 'Arabic (ar)' },
        { value: 'fa', text: 'Persian (fa)' },
        { value: 'th', text: 'Thai (th)' },
        { value: 'ko', text: 'Korean (ko)' },
        { value: 'ja', text: 'Japanese (ja)' },
        { value: 'zh', text: 'Chinese (zh)' },
        { value: 'ru', text: 'Russian (ru)' },
        { value: 'es', text: 'Spanish (es)' },
        { value: 'fr', text: 'French (fr)' },
        { value: 'de', text: 'German (de)' },
        { value: 'it', text: 'Italian (it)' },
        { value: 'pt', text: 'Portuguese (pt)' },
        { value: 'nl', text: 'Dutch (nl)' },
        { value: 'pl', text: 'Polish (pl)' },
        { value: 'tr', text: 'Turkish (tr)' },
        { value: 'vi', text: 'Vietnamese (vi)' },
        { value: 'id', text: 'Indonesian (id)' },
        { value: 'ms', text: 'Malay (ms)' }
      ],
      supportsBilingual: true,
      bilingualSeparator: ',',
      autoDetect: true
    }
  },

  // Function to handle bilingual language selection
  handleBilingualLanguageSelection() {
    const engine = selectedEngine;
    const engineConfig = ocrEngines[engine];
    
    if (!engineConfig || !engineConfig.supportsBilingual) {
      return;
    }
    
    const languageSelect = document.getElementById('language');
    const additionalLanguageSelect = document.getElementById('additional-language');
    
    if (!additionalLanguageSelect) {
      // Create additional language select if it doesn't exist
      const additionalLanguageDiv = document.createElement('div');
      additionalLanguageDiv.className = 'mb-4';
      additionalLanguageDiv.innerHTML = `
        <label class="block text-sm font-medium text-gray-700 mb-2">
          Additional Language (Optional)
        </label>
        <select id="additional-language" class="w-full p-2 text-sm border border-teal-200 rounded focus:border-peacock-primary">
          <option value="">None</option>
        </select>
        <p class="text-xs text-gray-500 mt-1">
          For bilingual/multilingual documents. Surya auto-detects languages.
        </p>
      `;
      
      languageSelect.parentNode.parentNode.appendChild(additionalLanguageDiv);
      
      // Populate additional language options
      updateAdditionalLanguageOptions();
    }
    
    // Show/hide additional language select based on engine
    const additionalLanguageDiv = document.getElementById('additional-language').parentNode;
    additionalLanguageDiv.style.display = engineConfig.supportsBilingual ? 'block' : 'none';
  },

  // Function to update additional language options
  updateAdditionalLanguageOptions() {
    const engine = selectedEngine;
    const engineConfig = ocrEngines[engine];
    const additionalLanguageSelect = document.getElementById('additional-language');
    
    if (!additionalLanguageSelect || !engineConfig) {
      return;
    }
    
    // Clear existing options
    additionalLanguageSelect.innerHTML = '<option value="">None</option>';
    
    // Add language options
    engineConfig.languages.forEach(lang => {
      const option = document.createElement('option');
      option.value = lang.value;
      option.textContent = lang.text;
      additionalLanguageSelect.appendChild(option);
    });
  },

  // Function to get combined language parameter
  getLanguageParameter() {
    const engine = selectedEngine;
    const engineConfig = ocrEngines[engine];
    const primaryLanguage = document.getElementById('language').value;
    const additionalLanguage = document.getElementById('additional-language')?.value;
    
    if (!engineConfig || !engineConfig.supportsBilingual || !additionalLanguage) {
      return primaryLanguage;
    }
    
    if (engine === 'tesseract') {
      // Tesseract uses + separator
      return `${primaryLanguage}+${additionalLanguage}`;
    } else if (engine === 'surya') {
      // Surya uses comma separator and supports additional_languages parameter
      return primaryLanguage;
    }
    
    return primaryLanguage;
  },

  // Function to get additional languages for Surya
  getAdditionalLanguages() {
    const engine = selectedEngine;
    const additionalLanguage = document.getElementById('additional-language')?.value;
    
    if (engine === 'surya' && additionalLanguage) {
      return [additionalLanguage];
    }
    
    return null;
  },

  init() {
    this.loadSettings();
    this.layoutClasses = this.getLayoutClasses();

    // Initialize content from the textarea if it exists
    const textarea = document.getElementById('content');
    if (textarea && textarea.value) {
      this.content = textarea.value;
    }

    // Set `imageZoom` only after the viewer is fully initialized.
    this.imageViewer = initializeImageViewer(IMAGE_URL);
    this.imageViewer.addHandler('open', () => {
      this.imageZoom = this.imageZoom || this.imageViewer.viewport.getHomeZoom();
      this.imageViewer.viewport.zoomTo(this.imageZoom);
    });

    // Use `.bind(this)` so that `this` in the function refers to this app and
    // not `window`.
    window.onbeforeunload = this.onBeforeUnload.bind(this);
    
    // Initialize language options
    this.updateLanguageOptions();
  },

  // Settings IO

  loadSettings() {
    const settingsStr = localStorage.getItem(CONFIG_KEY);
    if (settingsStr) {
      try {
        const settings = JSON.parse(settingsStr);
        this.textZoom = settings.textZoom || this.textZoom;
        // We can only get an accurate default zoom after the viewer is fully
        // initialized. See `init` for details.
        this.imageZoom = settings.imageZoom;
        this.layout = settings.layout || this.layout;

        this.fromScript = settings.fromScript || this.fromScript;
        this.toScript = settings.toScript || this.toScript;
        
        // Load OCR settings
        this.selectedEngine = settings.selectedEngine || this.selectedEngine;
        this.selectedLanguage = settings.selectedLanguage || this.selectedLanguage;
      } catch (error) {
        // Old settings are invalid -- rewrite with valid values.
        this.saveSettings();
      }
    }
  },
  saveSettings() {
    const settings = {
      textZoom: this.textZoom,
      imageZoom: this.imageZoom,
      layout: this.layout,
      fromScript: this.fromScript,
      toScript: this.toScript,
      selectedEngine: this.selectedEngine,
      selectedLanguage: this.selectedLanguage,
    };
    localStorage.setItem(CONFIG_KEY, JSON.stringify(settings));
  },
  getLayoutClasses() {
    if (this.layout === LAYOUT_TOP_AND_BOTTOM) {
      return CLASSES_TOP_AND_BOTTOM;
    }
    return CLASSES_SIDE_BY_SIDE;
  },

  // Callbacks

  /** Displays a warning dialog if the user has unsaved changes and tries to navigate away. */
  onBeforeUnload(e) {
    if (this.hasUnsavedChanges) {
      // Keeps the dialog event.
      return true;
    }
    // Cancels the dialog event.
    return null;
  },

  // OCR controls

  updateLanguageOptions() {
    const engine = selectedEngine;
    const engineConfig = ocrEngines[engine];
    const languageSelect = document.getElementById('language');
    
    if (!languageSelect || !engineConfig) {
      return;
    }
    
    // Clear existing options
    languageSelect.innerHTML = '';
    
    // Add language options
    engineConfig.languages.forEach(lang => {
      const option = document.createElement('option');
      option.value = lang.value;
      option.textContent = lang.text;
      languageSelect.appendChild(option);
    });
    
    // Handle bilingual language selection
    handleBilingualLanguageSelection();
  },

  async runOCR(engine = 'google', language = 'sa') {
    this.isRunningOCR = true;

    const { pathname } = window.location;
    const url = pathname.replace('/proofing/', '/api/ocr/') + `?engine=${engine}&language=${language}`;

    const content = await fetch(url)
      .then((response) => {
        if (response.ok) {
          return response.text();
        }
        return '(server error)';
      });
    
    // Update the Alpine.js data property directly
    this.content = content;
    
    // Also update the DOM element for compatibility
    const textarea = document.getElementById('content');
    if (textarea) {
      textarea.value = content;
    }

    this.isRunningOCR = false;
  },

  // Image zoom controls

  increaseImageZoom() {
    this.imageZoom *= 1.2;
    this.imageViewer.viewport.zoomTo(this.imageZoom);
    this.saveSettings();
  },
  decreaseImageZoom() {
    this.imageZoom *= 0.8;
    this.imageViewer.viewport.zoomTo(this.imageZoom);
    this.saveSettings();
  },
  resetImageZoom() {
    this.imageZoom = this.imageViewer.viewport.getHomeZoom();
    this.imageViewer.viewport.zoomTo(this.imageZoom);
    this.saveSettings();
  },

  // Text zoom controls

  increaseTextSize() {
    this.textZoom += 0.2;
    this.saveSettings();
  },
  decreaseTextSize() {
    this.textZoom = Math.max(0, this.textZoom - 0.2);
    this.saveSettings();
  },

  // Layout controls

  displaySideBySide() {
    this.layout = LAYOUT_SIDE_BY_SIDE;
    this.layoutClasses = this.getLayoutClasses();
    this.saveSettings();
  },
  displayTopAndBottom() {
    this.layout = LAYOUT_TOP_AND_BOTTOM;
    this.layoutClasses = this.getLayoutClasses();
    this.saveSettings();
  },

  // Markup controls

  changeSelectedText(callback) {
    // Get the textarea element
    const textarea = document.getElementById('content');
    if (!textarea) return;
    
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const { value } = textarea;

    const selectedText = value.substr(start, end - start);
    const replacement = callback(selectedText);
    const newValue = value.substr(0, start) + replacement + value.substr(end);
    
    // Update both the DOM element and Alpine.js data
    textarea.value = newValue;
    this.content = newValue;

    // Update selection state and focus for better UX.
    textarea.setSelectionRange(start, start + replacement.length);
    textarea.focus();
  },
  markAsError() {
    this.changeSelectedText((s) => `<error>${s}</error>`);
  },
  markAsFix() {
    this.changeSelectedText((s) => `<fix>${s}</fix>`);
  },
  markAsUnclear() {
    this.changeSelectedText((s) => `<flag>${s}</flag>`);
  },
  markAsFootnoteNumber() {
    this.changeSelectedText((s) => `[^${s}]`);
  },
  replaceColonVisarga() {
    this.changeSelectedText((s) => s.replaceAll(':', 'ः'));
  },
  replaceSAvagraha() {
    this.changeSelectedText((s) => s.replaceAll('S', 'ऽ'));
  },
  transliterateSelection() {
    this.changeSelectedText((s) => Sanscript.t(s, this.fromScript, this.toScript));
    this.saveSettings();
  },

  // Character controls
  copyCharacter(e) {
    const character = e.target.textContent;
    navigator.clipboard.writeText(character);
  },
});
