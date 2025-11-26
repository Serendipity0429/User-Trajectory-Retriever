// --- Color and Theme Logic ---

// Function to lighten or darken a hex color
function shadeColor(color, percent) {
    let R = parseInt(color.substring(1, 3), 16);
    let G = parseInt(color.substring(3, 5), 16);
    let B = parseInt(color.substring(5, 7), 16);

    R = parseInt(R * (100 + percent) / 100);
    G = parseInt(G * (100 + percent) / 100);
    B = parseInt(B * (100 + percent) / 100);

    R = (R < 255) ? R : 255;
    G = (G < 255) ? G : 255;
    B = (B < 255) ? B : 255;

    const RR = ((R.toString(16).length === 1) ? "0" + R.toString(16) : R.toString(16));
    const GG = ((G.toString(16).length === 1) ? "0" + G.toString(16) : G.toString(16));
    const BB = ((B.toString(16).length === 1) ? "0" + B.toString(16) : B.toString(16));

    return "#" + RR + GG + BB;
}

function getContrastingTextColor(hexcolor) {
    hexcolor = hexcolor.replace("#", "");
    const r = parseInt(hexcolor.substr(0, 2), 16);
    const g = parseInt(hexcolor.substr(2, 2), 16);
    const b = parseInt(hexcolor.substr(4, 2), 16);
    const yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000;
    return (yiq >= 128) ? '#000000' : '#ffffff';
}

function hexToRgb(hex) {
    hex = hex.replace("#", "");
    const r = parseInt(hex.substr(0, 2), 16);
    const g = parseInt(hex.substr(2, 2), 16);
    const b = parseInt(hex.substr(4, 2), 16);
    return { r, g, b };
}

function colorDistance(hex1, hex2) {
    const rgb1 = hexToRgb(hex1);
    const rgb2 = hexToRgb(hex2);
    const dr = rgb1.r - rgb2.r;
    const dg = rgb1.g - rgb2.g;
    const db = rgb1.b - rgb2.b;
    return Math.sqrt(dr * dr + dg * dg + db * db);
}

// Function to generate and apply the color palette
function applyColors(mainColor, isDarkMode) {
    console.log(`Applying colors. Main color: ${mainColor}, Dark mode: ${isDarkMode}`);
    const originalRed = '#ad0b2a';
    const elegantBlue = '#005f73';
    let dangerColor;

    // If the main color is too close to red, switch to the elegant blue.
    if (colorDistance(mainColor, originalRed) < 100) {
        dangerColor = elegantBlue;
    } else {
        dangerColor = originalRed;
    }
    
    const dangerTextColor = getContrastingTextColor(dangerColor);

    const colors = {
        '--primary-color': mainColor,
        '--primary-color-hover': shadeColor(mainColor, -10), // 10% darker
        '--primary-color-active': shadeColor(mainColor, -20), // 20% darker
        '--danger-color': dangerColor,
        '--danger-color-hover': shadeColor(dangerColor, -10),
        '--danger-text-color': dangerTextColor,
    };

    const root = document.documentElement;
    for (const [key, value] of Object.entries(colors)) {
        root.style.setProperty(key, value);
        console.log(`Set CSS variable ${key} to ${value}`);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    console.log("Page settings script loaded.");
    const colorThemeSelector = document.getElementById('color-theme-selector');
    const customColorPicker = document.getElementById('custom-color-picker');
    const darkModeSwitch = document.getElementById('darkModeSwitch');

    const themes = {
        'tsinghua-purple': '#671372',
        'klein-blue': '#002FA7',
        'renmin-red': '#ad0b2a',
        'prussian-blue': '#003153',
        'forest-green': '#1d3124',
        'dark-gray': '#2f2f2f',
        'dark-brown': '#5d3000'
    };
    const darkThemes = {
        'tsinghua-purple': '#d7bde2', // Lighter Purple
        'klein-blue': '#a9cce3',    // Lighter Blue
        'renmin-red': '#f5b7b1',    // Lighter Red
        'prussian-blue': '#aed6f1', // Even Lighter Blue
        'forest-green': '#a9dfbf', // Lighter Green
        'dark-gray': '#e5e7e9',   // Lighter Gray
        'dark-brown': '#f8c471'    // Lighter Orange/Brown
    };

    function applyCurrentTheme() {
        const isDarkMode = darkModeSwitch.checked;
        updatePaletteSwatches(isDarkMode);

        const activeColorOption = colorThemeSelector.querySelector('.color-option.active');
        const theme = activeColorOption ? activeColorOption.dataset.color : 'custom';
        const customColor = customColorPicker.value;
        applyTheme(theme, customColor);
    }

    function applyTheme(theme, customColor) {
        console.log(`Applying theme: ${theme}, Custom color: ${customColor}`);
        const isDarkMode = darkModeSwitch.checked;
        const selectedThemes = isDarkMode ? darkThemes : themes;
        const color = selectedThemes[theme] || (isDarkMode ? shadeColor(customColor, 50) : customColor) || selectedThemes['tsinghua-purple'];
        
        applyColors(color, isDarkMode);
    }

    function updatePaletteSwatches(isDarkMode) {
        const palette = isDarkMode ? darkThemes : themes;
        colorThemeSelector.querySelectorAll('.color-option').forEach(option => {
            const colorName = option.dataset.color;
            if (palette[colorName]) {
                option.style.backgroundColor = palette[colorName];
            }
        });
    }

    function saveSettings() {
        const activeColorOption = colorThemeSelector.querySelector('.color-option.active');
        const colorTheme = activeColorOption ? activeColorOption.dataset.color : 'custom';
        const customColor = customColorPicker.value;

        localStorage.setItem('colorTheme', colorTheme);
        localStorage.setItem('customColor', customColor);
        localStorage.setItem('darkMode', darkModeSwitch.checked ? 'enabled' : 'disabled');
        console.log("Settings saved.");
    }

    function loadSettings() {
        const colorTheme = localStorage.getItem('colorTheme') || 'tsinghua-purple';
        const customColor = localStorage.getItem('customColor') || '#671372';
        const darkMode = localStorage.getItem('darkMode') === 'enabled';

        darkModeSwitch.checked = darkMode;

        colorThemeSelector.querySelectorAll('.color-option').forEach(option => {
            option.classList.toggle('active', option.dataset.color === colorTheme);
        });
        
        if (colorTheme === 'custom') {
            customColorPicker.closest('.custom-color-wrapper').classList.add('active');
        }

        customColorPicker.value = customColor;
        
        applyCurrentTheme();
        console.log("Settings loaded.");
    }

    // Event Listeners
    darkModeSwitch.addEventListener('change', () => {
        console.log("Dark mode switch changed.");
        applyCurrentTheme();
        saveSettings();
    });

    colorThemeSelector.addEventListener('click', (event) => {
        if (event.target.classList.contains('color-option')) {
            console.log("Color option clicked.");
            event.stopPropagation();
            colorThemeSelector.querySelectorAll('.color-option').forEach(option => option.classList.remove('active'));
            event.target.classList.add('active');
            // Remove active class from custom color wrapper
            customColorPicker.closest('.custom-color-wrapper').classList.remove('active');
            const theme = event.target.dataset.color;
            applyTheme(theme, customColorPicker.value);
            saveSettings();
        }
    });

    customColorPicker.addEventListener('input', (event) => {
        console.log("Custom color picker input.");
        event.stopPropagation();
        const color = event.target.value;
        const isDarkMode = darkModeSwitch.checked;
        const finalColor = isDarkMode ? shadeColor(color, 50) : color; // Increased lightness
        applyColors(finalColor, isDarkMode);
        colorThemeSelector.querySelectorAll('.color-option').forEach(option => option.classList.remove('active'));
        // Add active class to the custom color wrapper
        customColorPicker.closest('.custom-color-wrapper').classList.add('active');
        saveSettings();
    });

    // Initial Load
    loadSettings();
});