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
function applyColors(mainColor) {
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
        '--secondary-color': '#f4f4f4',
        '--light-gray': '#f8f9fa',
        '--dark-gray': '#34495e',
        '--white': '#ffffff',
    };

    const root = document.documentElement;
    for (const [key, value] of Object.entries(colors)) {
        root.style.setProperty(key, value);
    }
}