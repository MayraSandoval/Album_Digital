tailwind.config = {
    theme: {
        extend: {
            colors: {
                // El acento "indigo" pasa a mezclar azul y violeta.
                indigo: {
                    50: '#eff6ff',
                    100: '#dbeafe',
                    200: '#bfdbfe',
                    300: '#93c5fd',
                    400: '#60a5fa',
                    500: '#6366f1',
                    600: '#7c3aed',
                    700: '#6d28d9',
                    800: '#5b21b6',
                    900: '#4c1d95',
                    950: '#2e1065',
                },
                brand: {
                    sky: '#38bdf8',
                    blue: '#3b82f6',
                    indigo: '#6366f1',
                    violet: '#8b5cf6',
                    purple: '#a855f7',
                },
            },
            backgroundImage: {
                'brand-gradient': 'linear-gradient(120deg, #38bdf8 0%, #6366f1 48%, #a855f7 100%)',
            },
            boxShadow: {
                'brand-glow': '0 0 24px -6px rgba(99, 102, 241, 0.55)',
            },
        },
    },
};
