module.exports = {
  content: [
    './kalanjiyam/static/js/*.js',
    './kalanjiyam/templates/**/*.html',
    './kalanjiyam/utils/parse_alignment.py',
    './kalanjiyam/utils/xml.py',
    './kalanjiyam/views/proofing/main.py',
    './kalanjiyam/static/js/proofer.js',
  ],
  safelist: [
      // Used by Flask-admin internally -- include it explicitly
      "pagination",
      // Custom height classes used in proofing interface
      "h-[90vh]",
      // Arbitrary value classes that might be used
      "h-[90vh]",
      "grid-cols-6",
      "grid-cols-8", 
      "grid-cols-10",
      "w-48",
      "w-60",
      "w-80",
  ],
  plugins: [
    require('@tailwindcss/typography')({
      className: 'tw-prose',
    }),
  ]
}
