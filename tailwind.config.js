module.exports = {
  content: [
    './kalanjiyam/static/js/*.js',
    './kalanjiyam/templates/**/*.html',
    './kalanjiyam/utils/parse_alignment.py',
    './kalanjiyam/utils/xml.py',
    './kalanjiyam/views/proofing/main.py',
  ],
  safelist: [
      // Used by Flask-admin internally -- include it explicitly
      "pagination",
  ],
  plugins: [
    require('@tailwindcss/typography')({
      className: 'tw-prose',
    }),
  ]
}
