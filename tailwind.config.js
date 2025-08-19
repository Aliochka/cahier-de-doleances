/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class', // on pilote le mode sombre via la classe .dark sur <html>
  content: [
    "./app/templates/**/*.html",
    "./app/**/*.py" // utile si tu injectes des classes dans des strings Python
  ],
  theme: {
    extend: {
      colors: {
        paper:  "#FFF7E6",
        ink:    "#1A1A1A",
        ink2:   "#57534E",
        line:   "#E7E2DA",
        accent: "#1F3A5F",
        d_bg:   "#0E1013",
        d_card: "#151821",
        d_line: "#242938",
        d_ink:  "#EDEDED",
        d_ink2: "#B5B8BE",
        d_accent:"#8AB6FF"
      },
      fontFamily: {
        mono: ['IBM Plex Mono', 'ui-monospace','SFMono-Regular','Menlo','monospace'],
        ui: ['Inter','ui-sans-serif','system-ui','-apple-system','Segoe UI','Roboto','sans-serif']
      },
      boxShadow: {
        sheet: '0 1px 2px rgba(0,0,0,.03), 0 6px 24px rgba(0,0,0,.04)'
      }
    }
  },
  plugins: []
}
