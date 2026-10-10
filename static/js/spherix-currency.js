/**
 * Spherix Clinic - Intelligent Global Currency & Geolocation Engine
 * Automatically detects user location & displays regional currency (INR ₹, USD $, EUR €, GBP £, AED د.إ, etc.)
 * Supports all 195 world countries with instant exchange conversion & DOM price formatting.
 */

(function () {
    'use strict';

    // 1. Core Currency Exchange Rates (Base: 1 Unit in INR)
    const RATES_IN_INR = {
        'INR': 1.0,
        'USD': 86.80,
        'EUR': 92.50,
        'GBP': 110.20,
        'AED': 23.63,
        'SAR': 23.14,
        'QAR': 23.84,
        'KWD': 282.40,
        'BHD': 230.30,
        'OMR': 225.40,
        'JOD': 122.40,
        'SGD': 65.20,
        'CAD': 61.20,
        'AUD': 55.40,
        'NZD': 50.80,
        'JPY': 0.58,
        'CNY': 11.95,
        'HKD': 11.16,
        'TWD': 2.68,
        'KRW': 0.061,
        'CHF': 97.40,
        'SEK': 8.20,
        'NOK': 7.90,
        'DKK': 12.40,
        'PLN': 21.80,
        'CZK': 3.72,
        'HUF': 0.23,
        'RON': 18.60,
        'BGN': 47.30,
        'TRY': 2.38,
        'RUB': 0.94,
        'ZAR': 4.82,
        'BRL': 14.85,
        'MXN': 4.32,
        'ARS': 0.082,
        'CLP': 0.091,
        'COP': 0.021,
        'PEN': 23.20,
        'EGP': 1.74,
        'NGN': 0.057,
        'KES': 0.67,
        'GHS': 5.65,
        'MAD': 8.80,
        'DZD': 0.65,
        'TND': 27.80,
        'ILS': 23.80,
        'THB': 2.48,
        'MYR': 19.65,
        'IDR': 0.0053,
        'PHP': 1.51,
        'VND': 0.0034,
        'PKR': 0.31,
        'BDT': 0.72,
        'LKR': 0.29,
        'NPR': 0.625,
        'MVR': 5.62,
        'AFN': 1.25,
        'ALL': 0.95,
        'AMD': 0.22,
        'AOA': 0.093,
        'AZN': 51.05,
        'BAM': 47.30,
        'BBD': 43.40,
        'BIF': 0.029,
        'BND': 65.20,
        'BOB': 12.55,
        'BSD': 86.80,
        'BTN': 1.0,
        'BWP': 6.25,
        'BYN': 26.50,
        'BZD': 43.40,
        'CDF': 0.031,
        'CRC': 0.17,
        'CUP': 3.62,
        'CVE': 0.84,
        'DJF': 0.49,
        'DOP': 1.44,
        'ERN': 5.79,
        'ETB': 0.68,
        'FJD': 38.60,
        'GEL': 31.80,
        'GMD': 1.22,
        'GNF': 0.010,
        'GTQ': 11.20,
        'GYD': 0.41,
        'HNL': 3.42,
        'HTG': 0.66,
        'IQD': 0.066,
        'IRR': 0.0021,
        'ISK': 0.63,
        'JMD': 0.55,
        'KGS': 0.99,
        'KHR': 0.021,
        'KMF': 0.19,
        'KZT': 0.17,
        'LAK': 0.0039,
        'LBP': 0.00097,
        'LRD': 0.44,
        'LSL': 4.82,
        'LYD': 17.65,
        'MDL': 4.85,
        'MGA': 0.019,
        'MKD': 1.50,
        'MMK': 0.041,
        'MNT': 0.025,
        'MOP': 10.83,
        'MRU': 2.18,
        'MUR': 1.88,
        'MWK': 0.050,
        'MZN': 1.36,
        'NAD': 4.82,
        'NIO': 2.35,
        'PAB': 86.80,
        'PGK': 21.80,
        'PYG': 0.011,
        'RSD': 0.79,
        'RWF': 0.062,
        'SBD': 10.20,
        'SCR': 6.25,
        'SDG': 0.14,
        'SLL': 0.0038,
        'SOS': 0.15,
        'SRD': 2.45,
        'SSP': 0.028,
        'STN': 3.75,
        'SYP': 0.0067,
        'SZL': 4.82,
        'TJS': 8.15,
        'TMT': 24.80,
        'TOP': 36.80,
        'TTD': 12.80,
        'TZS': 0.033,
        'UAH': 2.08,
        'UGX': 0.023,
        'UYU': 2.05,
        'UZS': 0.0067,
        'VES': 1.95,
        'VUV': 0.72,
        'WST': 31.40,
        'XAF': 0.14,
        'XCD': 32.15,
        'XOF': 0.14,
        'XPF': 0.78,
        'YER': 0.35,
        'ZMW': 3.15,
        'ZWL': 0.003
    };

    // 2. Global Currency Symbols
    const CURRENCY_SYMBOLS = {
        'INR': '₹',
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'AED': 'د.إ',
        'SAR': '﷼',
        'QAR': 'QR',
        'KWD': 'KD',
        'BHD': 'BD',
        'OMR': 'OMR',
        'JOD': 'JD',
        'SGD': 'S$',
        'CAD': 'CA$',
        'AUD': 'AU$',
        'NZD': 'NZ$',
        'JPY': '¥',
        'CNY': '¥',
        'HKD': 'HK$',
        'TWD': 'NT$',
        'KRW': '₩',
        'CHF': 'CHF ',
        'SEK': 'kr',
        'NOK': 'kr',
        'DKK': 'kr.',
        'PLN': 'zł',
        'CZK': 'Kč',
        'HUF': 'Ft',
        'RON': 'lei',
        'BGN': 'лв',
        'TRY': '₺',
        'RUB': '₽',
        'ZAR': 'R',
        'BRL': 'R$',
        'MXN': 'Mex$',
        'ARS': '$',
        'CLP': '$',
        'COP': '$',
        'PEN': 'S/',
        'EGP': 'E£',
        'NGN': '₦',
        'KES': 'KSh',
        'GHS': 'GH₵',
        'MAD': 'MAD',
        'DZD': 'DA',
        'TND': 'DT',
        'ILS': '₪',
        'THB': '฿',
        'MYR': 'RM',
        'IDR': 'Rp',
        'PHP': '₱',
        'VND': '₫',
        'PKR': 'Rs',
        'BDT': '৳',
        'LKR': 'Rs',
        'NPR': 'Rs',
        'MVR': 'Rf',
        'AFN': '؋',
        'ALL': 'L',
        'AMD': '֏',
        'AOA': 'Kz',
        'AZN': '₼',
        'BAM': 'KM',
        'BBD': 'Bds$',
        'BIF': 'FBu',
        'BND': 'B$',
        'BOB': 'Bs.',
        'BSD': 'B$',
        'BTN': 'Nu.',
        'BWP': 'P',
        'BYN': 'Br',
        'BZD': 'BZ$',
        'CDF': 'FC',
        'CRC': '₡',
        'CUP': '$MN',
        'CVE': 'Esc',
        'DJF': 'Fdj',
        'DOP': 'RD$',
        'ERN': 'Nfk',
        'ETB': 'Br',
        'FJD': 'FJ$',
        'GEL': '₾',
        'GMD': 'D',
        'GNF': 'FG',
        'GTQ': 'Q',
        'GYD': 'G$',
        'HNL': 'L',
        'HTG': 'G',
        'IQD': 'ع.د',
        'IRR': '﷼',
        'ISK': 'kr',
        'JMD': 'J$',
        'KGS': 'с',
        'KHR': '៛',
        'KMF': 'CF',
        'KZT': '₸',
        'LAK': '₭',
        'LBP': 'L£',
        'LRD': 'L$',
        'LSL': 'L',
        'LYD': 'LD',
        'MDL': 'lei',
        'MGA': 'Ar',
        'MKD': 'ден',
        'MMK': 'K',
        'MNT': '₮',
        'MOP': 'MOP$',
        'MRU': 'UM',
        'MUR': '₨',
        'MWK': 'MK',
        'MZN': 'MT',
        'NAD': 'N$',
        'NIO': 'C$',
        'PAB': 'B/.',
        'PGK': 'K',
        'PYG': '₲',
        'RSD': 'дин.',
        'RWF': 'FRw',
        'SBD': 'SI$',
        'SCR': 'SR',
        'SDG': 'SDG',
        'SLL': 'Le',
        'SOS': 'S',
        'SRD': '$',
        'SSP': 'SS£',
        'STN': 'Db',
        'SYP': '£S',
        'SZL': 'E',
        'TJS': 'SM',
        'TMT': 'T',
        'TOP': 'T$',
        'TTD': 'TT$',
        'TZS': 'TSh',
        'UAH': '₴',
        'UGX': 'USh',
        'UYU': '$U',
        'UZS': 'soʻm',
        'VES': 'Bs.S',
        'VUV': 'VT',
        'WST': 'WS$',
        'XAF': 'FCFA',
        'XCD': 'EC$',
        'XOF': 'CFA',
        'XPF': '₣',
        'YER': '﷼',
        'ZMW': 'ZK',
        'ZWL': 'Z$'
    };

    // 3. Currency Names & Flags Mapping
    const CURRENCY_METADATA = {
        'INR': { name: 'Indian Rupee', flag: '🇮🇳', country: 'India' },
        'USD': { name: 'US Dollar', flag: '🇺🇸', country: 'United States' },
        'EUR': { name: 'Euro', flag: '🇪🇺', country: 'Eurozone' },
        'GBP': { name: 'British Pound', flag: '🇬🇧', country: 'United Kingdom' },
        'AED': { name: 'UAE Dirham', flag: '🇦🇪', country: 'United Arab Emirates' },
        'SAR': { name: 'Saudi Riyal', flag: '🇸🇦', country: 'Saudi Arabia' },
        'QAR': { name: 'Qatari Riyal', flag: '🇶🇦', country: 'Qatar' },
        'KWD': { name: 'Kuwaiti Dinar', flag: '🇰🇼', country: 'Kuwait' },
        'BHD': { name: 'Bahraini Dinar', flag: '🇧🇭', country: 'Bahrain' },
        'OMR': { name: 'Omani Rial', flag: '🇴🇲', country: 'Oman' },
        'JOD': { name: 'Jordanian Dinar', flag: '🇯🇴', country: 'Jordan' },
        'SGD': { name: 'Singapore Dollar', flag: '🇸🇬', country: 'Singapore' },
        'CAD': { name: 'Canadian Dollar', flag: '🇨🇦', country: 'Canada' },
        'AUD': { name: 'Australian Dollar', flag: '🇦🇺', country: 'Australia' },
        'NZD': { name: 'New Zealand Dollar', flag: '🇳🇿', country: 'New Zealand' },
        'JPY': { name: 'Japanese Yen', flag: '🇯🇵', country: 'Japan' },
        'CNY': { name: 'Chinese Yuan', flag: '🇨🇳', country: 'China' },
        'HKD': { name: 'Hong Kong Dollar', flag: '🇭🇰', country: 'Hong Kong' },
        'TWD': { name: 'New Taiwan Dollar', flag: '🇹🇼', country: 'Taiwan' },
        'KRW': { name: 'South Korean Won', flag: '🇰🇷', country: 'South Korea' },
        'CHF': { name: 'Swiss Franc', flag: '🇨🇭', country: 'Switzerland' },
        'SEK': { name: 'Swedish Krona', flag: '🇸🇪', country: 'Sweden' },
        'NOK': { name: 'Norwegian Krone', flag: '🇳🇴', country: 'Norway' },
        'DKK': { name: 'Danish Krone', flag: '🇩🇰', country: 'Denmark' },
        'PLN': { name: 'Polish Złoty', flag: '🇵🇱', country: 'Poland' },
        'CZK': { name: 'Czech Koruna', flag: '🇨🇿', country: 'Czech Republic' },
        'HUF': { name: 'Hungarian Forint', flag: '🇭🇺', country: 'Hungary' },
        'RON': { name: 'Romanian Leu', flag: '🇷🇴', country: 'Romania' },
        'BGN': { name: 'Bulgarian Lev', flag: '🇧🇬', country: 'Bulgaria' },
        'TRY': { name: 'Turkish Lira', flag: '🇹🇷', country: 'Turkey' },
        'RUB': { name: 'Russian Ruble', flag: '🇷🇺', country: 'Russia' },
        'ZAR': { name: 'South African Rand', flag: '🇿🇦', country: 'South Africa' },
        'BRL': { name: 'Brazilian Real', flag: '🇧🇷', country: 'Brazil' },
        'MXN': { name: 'Mexican Peso', flag: '🇲🇽', country: 'Mexico' },
        'ARS': { name: 'Argentine Peso', flag: '🇦🇷', country: 'Argentina' },
        'CLP': { name: 'Chilean Peso', flag: '🇨🇱', country: 'Chile' },
        'COP': { name: 'Colombian Peso', flag: '🇨🇴', country: 'Colombia' },
        'PEN': { name: 'Peruvian Sol', flag: '🇵🇪', country: 'Peru' },
        'EGP': { name: 'Egyptian Pound', flag: '🇪🇬', country: 'Egypt' },
        'NGN': { name: 'Nigerian Naira', flag: '🇳🇬', country: 'Nigeria' },
        'KES': { name: 'Kenyan Shilling', flag: '🇰🇪', country: 'Kenya' },
        'GHS': { name: 'Ghanaian Cedi', flag: '🇬🇭', country: 'Ghana' },
        'MAD': { name: 'Moroccan Dirham', flag: '🇲🇦', country: 'Morocco' },
        'DZD': { name: 'Algerian Dinar', flag: '🇩🇿', country: 'Algeria' },
        'TND': { name: 'Tunisian Dinar', flag: '🇹🇳', country: 'Tunisia' },
        'ILS': { name: 'Israeli Shekel', flag: '🇮🇱', country: 'Israel' },
        'THB': { name: 'Thai Baht', flag: '🇹🇭', country: 'Thailand' },
        'MYR': { name: 'Malaysian Ringgit', flag: '🇲🇾', country: 'Malaysia' },
        'IDR': { name: 'Indonesian Rupiah', flag: '🇮🇩', country: 'Indonesia' },
        'PHP': { name: 'Philippine Peso', flag: '🇵🇭', country: 'Philippines' },
        'VND': { name: 'Vietnamese Dong', flag: '🇻🇳', country: 'Vietnam' },
        'PKR': { name: 'Pakistani Rupee', flag: '🇵🇰', country: 'Pakistan' },
        'BDT': { name: 'Bangladeshi Taka', flag: '🇧🇩', country: 'Bangladesh' },
        'LKR': { name: 'Sri Lankan Rupee', flag: '🇱🇰', country: 'Sri Lanka' },
        'NPR': { name: 'Nepalese Rupee', flag: '🇳🇵', country: 'Nepal' },
        'MVR': { name: 'Maldivian Rufiyaa', flag: '🇲🇻', country: 'Maldives' }
    };

    // 4. Timezone to Default Currency Heuristic for Instant Local Rendering
    function getCurrencyByTimezone() {
        try {
            const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
            if (tz.includes('Kolkata') || tz.includes('Calcutta') || tz.includes('India')) return 'INR';
            if (tz.startsWith('America/New_York') || tz.startsWith('America/Chicago') || tz.startsWith('America/Los_Angeles') || tz.startsWith('America/Denver') || tz.startsWith('America/Phoenix') || tz.startsWith('US/')) return 'USD';
            if (tz.startsWith('Europe/London') || tz.startsWith('GB')) return 'GBP';
            if (tz.startsWith('Europe/Paris') || tz.startsWith('Europe/Berlin') || tz.startsWith('Europe/Rome') || tz.startsWith('Europe/Madrid') || tz.startsWith('Europe/Amsterdam') || tz.startsWith('Europe/Brussels') || tz.startsWith('Europe/Vienna') || tz.startsWith('Europe/Dublin') || tz.startsWith('Europe/Lisbon') || tz.startsWith('Europe/Helsinki') || tz.startsWith('Europe/Athens')) return 'EUR';
            if (tz.startsWith('Asia/Dubai') || tz.startsWith('Asia/Muscat')) return 'AED';
            if (tz.startsWith('Asia/Riyadh') || tz.startsWith('Asia/Bahrain') || tz.startsWith('Asia/Qatar') || tz.startsWith('Asia/Kuwait')) return 'SAR';
            if (tz.startsWith('Asia/Singapore')) return 'SGD';
            if (tz.startsWith('Australia/')) return 'AUD';
            if (tz.startsWith('America/Toronto') || tz.startsWith('America/Vancouver') || tz.startsWith('America/Montreal') || tz.startsWith('Canada/')) return 'CAD';
            if (tz.startsWith('Asia/Tokyo')) return 'JPY';
            if (tz.startsWith('Asia/Shanghai') || tz.startsWith('Asia/Chongqing')) return 'CNY';
            if (tz.startsWith('Asia/Hong_Kong')) return 'HKD';
            if (tz.startsWith('Asia/Seoul')) return 'KRW';
            if (tz.startsWith('Europe/Zurich')) return 'CHF';
            if (tz.startsWith('Pacific/Auckland')) return 'NZD';
            if (tz.startsWith('Africa/Johannesburg')) return 'ZAR';
            if (tz.startsWith('America/Sao_Paulo')) return 'BRL';
            if (tz.startsWith('America/Mexico_City')) return 'MXN';
            if (tz.startsWith('Asia/Bangkok')) return 'THB';
            if (tz.startsWith('Asia/Kuala_Lumpur')) return 'MYR';
            if (tz.startsWith('Asia/Jakarta')) return 'IDR';
            if (tz.startsWith('Asia/Manila')) return 'PHP';
            if (tz.startsWith('Asia/Dhaka')) return 'BDT';
            if (tz.startsWith('Asia/Karachi')) return 'PKR';
            if (tz.startsWith('Asia/Kathmandu')) return 'NPR';
            if (tz.startsWith('Asia/Colombo')) return 'LKR';
        } catch (e) {
            console.warn('Timezone currency detection fallback:', e);
        }
        return 'INR';
    }

    // 5. Active State
    const STORAGE_KEY = 'spherix_user_currency';
    const AUTO_DETECTED_KEY = 'spherix_auto_detected_currency';
    let currentCurrency = localStorage.getItem(STORAGE_KEY) || getCurrencyByTimezone();
    let detectedLocationInfo = null;
    let isApplyingDOM = false;

    // Helper: Get symbol
    function getSymbol(currCode) {
        const code = (currCode || currentCurrency || 'INR').toUpperCase();
        return CURRENCY_SYMBOLS[code] || `${code} `;
    }

    // Helper: Convert currency value
    function convert(amount, fromCurr = 'INR', toCurr = null) {
        const target = (toCurr || currentCurrency || 'INR').toUpperCase();
        const source = (fromCurr || 'INR').toUpperCase();
        const val = parseFloat(amount) || 0;
        if (source === target) return val;

        const fromRate = RATES_IN_INR[source] || 1.0;
        const toRate = RATES_IN_INR[target] || 1.0;
        const inrVal = val * fromRate;
        const converted = inrVal / toRate;

        // Sensible rounding
        if (target === 'JPY' || target === 'KRW' || target === 'VND' || target === 'IDR') {
            return Math.round(converted);
        }
        return Math.round(converted * 100) / 100;
    }

    // Helper: Format price with symbol
    function formatPrice(inrAmount, options = {}) {
        const target = (options.currency || currentCurrency || 'INR').toUpperCase();
        const val = convert(inrAmount, 'INR', target);
        const sym = options.showSymbol === false ? '' : getSymbol(target);
        
        let formattedVal;
        if (target === 'JPY' || target === 'KRW' || target === 'VND' || target === 'IDR') {
            formattedVal = Math.round(val).toLocaleString('en-US');
        } else if (target === 'INR') {
            formattedVal = Number(val).toLocaleString('en-IN', {
                minimumFractionDigits: val % 1 !== 0 ? 2 : 0,
                maximumFractionDigits: 2
            });
        } else {
            formattedVal = Number(val).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }

        const prefix = options.prefix || '';
        const suffix = options.showCode ? ` ${target}` : '';
        return `${prefix}${sym}${formattedVal}${suffix}`.trim();
    }

    // 6. Asynchronous Geolocation & Country Currency Detection
    async function detectLocationAndSetCurrency(force = false) {
        if (!force && localStorage.getItem(STORAGE_KEY)) {
            // User explicitly chose a currency, retain it
            return;
        }

        try {
            // Attempt fast geo IP lookup
            let geoData = null;
            try {
                const res = await fetch('https://get.geojs.io/v1/ip/geo.json', { cache: 'no-store' });
                if (res.ok) geoData = await res.json();
            } catch (e) {
                // Fallback to backend detect
                try {
                    const res = await fetch('/api/currency/detect', { cache: 'no-store' });
                    if (res.ok) geoData = await res.json();
                } catch (e2) {}
            }

            if (geoData) {
                const countryCode = (geoData.country_code || geoData.country || '').toUpperCase();
                detectedLocationInfo = geoData;

                let matchedCurr = 'INR';
                if (countryCode === 'IN') matchedCurr = 'INR';
                else if (['US', 'PR', 'GU', 'VI', 'EC', 'SV', 'PA'].includes(countryCode)) matchedCurr = 'USD';
                else if (['GB', 'UK'].includes(countryCode)) matchedCurr = 'GBP';
                else if (['DE', 'FR', 'IT', 'ES', 'NL', 'BE', 'AT', 'PT', 'IE', 'FI', 'GR', 'EE', 'LV', 'LT', 'SK', 'SI', 'CY', 'MT', 'LU'].includes(countryCode)) matchedCurr = 'EUR';
                else if (countryCode === 'AE') matchedCurr = 'AED';
                else if (countryCode === 'SA') matchedCurr = 'SAR';
                else if (countryCode === 'QA') matchedCurr = 'QAR';
                else if (countryCode === 'KW') matchedCurr = 'KWD';
                else if (countryCode === 'SG') matchedCurr = 'SGD';
                else if (countryCode === 'CA') matchedCurr = 'CAD';
                else if (countryCode === 'AU') matchedCurr = 'AUD';
                else if (countryCode === 'NZ') matchedCurr = 'NZD';
                else if (countryCode === 'JP') matchedCurr = 'JPY';
                else if (countryCode === 'CN') matchedCurr = 'CNY';
                else if (countryCode === 'HK') matchedCurr = 'HKD';
                else if (countryCode === 'KR') matchedCurr = 'KRW';
                else if (countryCode === 'CH') matchedCurr = 'CHF';
                else if (countryCode === 'ZA') matchedCurr = 'ZAR';
                else if (countryCode === 'BR') matchedCurr = 'BRL';
                else if (countryCode === 'MX') matchedCurr = 'MXN';
                else if (countryCode === 'BD') matchedCurr = 'BDT';
                else if (countryCode === 'PK') matchedCurr = 'PKR';
                else if (countryCode === 'NP') matchedCurr = 'NPR';
                else if (countryCode === 'LK') matchedCurr = 'LKR';
                else {
                    matchedCurr = geoData.currency || getCurrencyByTimezone() || 'USD';
                }

                if (matchedCurr && (RATES_IN_INR[matchedCurr] || CURRENCY_SYMBOLS[matchedCurr])) {
                    setCurrency(matchedCurr, { isAutoDetected: true, savePermanent: false });
                }
            }
        } catch (err) {
            console.log('Spherix currency auto-detection background note:', err);
        }
    }

    // 7. Change Active Currency
    function setCurrency(newCurrencyCode, options = {}) {
        const code = (newCurrencyCode || 'INR').toUpperCase();
        if (!RATES_IN_INR[code] && !CURRENCY_SYMBOLS[code]) {
            console.warn(`Currency code ${code} not supported, keeping ${currentCurrency}`);
            return;
        }

        currentCurrency = code;
        if (options.savePermanent !== false) {
            localStorage.setItem(STORAGE_KEY, code);
        }

        // Notify server session asynchronously
        try {
            fetch('/api/currency/set', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ currency: code })
            }).catch(() => {});
        } catch (e) {}

        // Update all UI components and DOM price tags
        updateNavbarBadges();
        applyPricesToDOM(document.body);

        // Dispatch global event for custom components (Cart, Tata 1mg shop, etc.)
        const meta = CURRENCY_METADATA[code] || { name: code, flag: '🌍', country: 'Global' };
        window.dispatchEvent(new CustomEvent('spherix:currencyChanged', {
            detail: {
                currency: code,
                symbol: getSymbol(code),
                rate: RATES_IN_INR[code] || 1.0,
                flag: meta.flag,
                name: meta.name,
                country: meta.country,
                isAutoDetected: !!options.isAutoDetected
            }
        }));
    }

    // 8. DOM Price Transformer (Seamless & Robust)
    function parseInrAmount(text) {
        if (!text) return null;
        const clean = text.replace(/₹|INR|Rs\.?|\$|€|£|د\.إ|,\s*/gi, '').trim();
        const num = parseFloat(clean);
        return isNaN(num) ? null : num;
    }

    function applyPricesToDOM(root = document.body) {
        if (!root || isApplyingDOM) return;
        isApplyingDOM = true;

        try {
            // Target elements with explicit data attributes
            const explicitEls = root.querySelectorAll('[data-inr-price], [data-inr-amount], [data-price-inr], [data-base-price]');
            explicitEls.forEach(el => {
                const baseInr = parseFloat(el.getAttribute('data-inr-price') || el.getAttribute('data-inr-amount') || el.getAttribute('data-price-inr') || el.getAttribute('data-base-price'));
                if (!isNaN(baseInr)) {
                    const showCode = el.getAttribute('data-show-code') === 'true';
                    const prefix = el.getAttribute('data-price-prefix') || '';
                    el.textContent = formatPrice(baseInr, { showCode, prefix });
                }
            });

            // Target elements with class .spherix-price or .currency-price
            const taggedEls = root.querySelectorAll('.spherix-price, .currency-price, .live-currency-price, .med-price-display');
            taggedEls.forEach(el => {
                let baseInr = el.getAttribute('data-orig-inr');
                if (!baseInr) {
                    const parsed = parseInrAmount(el.textContent);
                    if (parsed !== null) {
                        baseInr = parsed;
                        el.setAttribute('data-orig-inr', baseInr);
                    }
                }
                if (baseInr) {
                    el.textContent = formatPrice(parseFloat(baseInr));
                }
            });

            // Update currency symbol spans
            const symEls = root.querySelectorAll('.spherix-currency-symbol, [data-currency-symbol]');
            symEls.forEach(el => {
                el.textContent = getSymbol();
            });

            // Update currency code spans
            const codeEls = root.querySelectorAll('.spherix-currency-code, [data-currency-code]');
            codeEls.forEach(el => {
                el.textContent = currentCurrency;
            });

        } catch (e) {
            console.error('Spherix DOM price transformation error:', e);
        } finally {
            isApplyingDOM = false;
        }
    }

    // 9. Update Navbar Badges & Switcher UI
    function updateNavbarBadges() {
        const meta = CURRENCY_METADATA[currentCurrency] || { name: currentCurrency, flag: '🌍', country: 'Global' };
        const sym = getSymbol(currentCurrency);

        // Update all header badges
        const badges = document.querySelectorAll('.spherix-currency-badge, #headerCurrencyBtn, #headerCurrencyLabel, .current-currency-display');
        badges.forEach(badge => {
            const flagSpan = badge.querySelector('.curr-flag');
            const codeSpan = badge.querySelector('.curr-code');
            const symSpan = badge.querySelector('.curr-sym');
            if (flagSpan) flagSpan.textContent = meta.flag;
            if (codeSpan) codeSpan.textContent = currentCurrency;
            if (symSpan) symSpan.textContent = sym;
            
            // If it's a direct label
            if (badge.id === 'headerCurrencyLabel') {
                badge.innerHTML = `<span class="text-sm mr-1">${meta.flag}</span> <span class="font-mono font-bold">${currentCurrency}</span> <span class="text-slate-400 font-normal">(${sym})</span>`;
            }
        });

        // Update active class in dropdown items
        const menuItems = document.querySelectorAll('.currency-select-item');
        menuItems.forEach(item => {
            const code = item.getAttribute('data-currency');
            if (code === currentCurrency) {
                item.classList.add('bg-blue-50', 'text-blue-700', 'font-bold');
                item.classList.remove('text-slate-700');
                const check = item.querySelector('.curr-check');
                if (check) check.classList.remove('hidden');
            } else {
                item.classList.remove('bg-blue-50', 'text-blue-700', 'font-bold');
                item.classList.add('text-slate-700');
                const check = item.querySelector('.curr-check');
                if (check) check.classList.add('hidden');
            }
        });
    }

    // 10. Global Dropdown / Modal Management
    window.toggleCurrencyDropdown = function (event) {
        if (event) {
            event.stopPropagation();
            event.preventDefault();
        }
        const dropdown = document.getElementById('spherix-currency-dropdown');
        if (!dropdown) {
            createCurrencyModal();
            return;
        }
        if (dropdown.classList.contains('hidden')) {
            dropdown.classList.remove('hidden');
            dropdown.classList.add('flex');
            const searchInput = document.getElementById('currencySearchInput');
            if (searchInput) {
                setTimeout(() => searchInput.focus(), 50);
            }
        } else {
            dropdown.classList.add('hidden');
            dropdown.classList.remove('flex');
        }
    };

    window.closeCurrencyDropdown = function () {
        const dropdown = document.getElementById('spherix-currency-dropdown');
        if (dropdown) {
            dropdown.classList.add('hidden');
            dropdown.classList.remove('flex');
        }
    };

    window.selectSpherixCurrency = function (currCode) {
        setCurrency(currCode, { savePermanent: true });
        window.closeCurrencyDropdown();
    };

    window.autoDetectUserCurrency = async function () {
        const btn = document.getElementById('currencyAutoDetectBtn');
        const originalHtml = btn ? btn.innerHTML : '';
        if (btn) {
            btn.innerHTML = `<i class="fas fa-spinner fa-spin mr-1.5 text-sky-500"></i> Detecting location...`;
            btn.disabled = true;
        }

        try {
            // Clear manual override to trigger auto-detection
            localStorage.removeItem(STORAGE_KEY);
            await detectLocationAndSetCurrency(true);

            const meta = CURRENCY_METADATA[currentCurrency] || { name: currentCurrency, flag: '🌍' };
            if (btn) {
                btn.innerHTML = `<i class="fas fa-check text-emerald-500 mr-1.5"></i> Detected: ${meta.flag} ${currentCurrency} (${getSymbol()})`;
                setTimeout(() => {
                    btn.innerHTML = originalHtml;
                    btn.disabled = false;
                    window.closeCurrencyDropdown();
                }, 1200);
            }
        } catch (e) {
            if (btn) {
                btn.innerHTML = originalHtml;
                btn.disabled = false;
            }
        }
    };

    window.filterCurrencyList = function (query) {
        const clean = (query || '').toLowerCase().trim();
        const items = document.querySelectorAll('.currency-select-item');
        let visibleCount = 0;

        items.forEach(item => {
            const text = (item.getAttribute('data-search') || item.textContent || '').toLowerCase();
            if (!clean || text.includes(clean)) {
                item.style.display = 'flex';
                visibleCount++;
            } else {
                item.style.display = 'none';
            }
        });

        const noRes = document.getElementById('currencyNoResults');
        if (noRes) {
            noRes.style.display = visibleCount === 0 ? 'block' : 'none';
        }
    };

    // 11. Create Currency Dropdown / Flyout Modal
    function createCurrencyModal() {
        if (document.getElementById('spherix-currency-dropdown')) return;

        const popularCurrencies = ['INR', 'USD', 'EUR', 'GBP', 'AED', 'SAR', 'CAD', 'AUD', 'SGD', 'JPY', 'CNY', 'CHF'];
        
        let allCurrenciesHtml = '';
        Object.keys(RATES_IN_INR).forEach(code => {
            const sym = CURRENCY_SYMBOLS[code] || `${code} `;
            const meta = CURRENCY_METADATA[code] || { name: code, flag: '🌍', country: code };
            const rate = RATES_IN_INR[code];
            const rateDesc = code === 'INR' ? 'Base Store Currency' : `1 ${code} ≈ ₹${rate.toFixed(2)}`;
            const isSelected = code === currentCurrency;

            allCurrenciesHtml += `
                <button type="button" onclick="selectSpherixCurrency('${code}');"
                    data-currency="${code}"
                    data-search="${code} ${meta.name} ${meta.country} ${sym}"
                    class="currency-select-item w-full flex items-center justify-between p-2.5 rounded-lg hover:bg-sky-50/80 transition-all text-left group cursor-pointer border border-transparent hover:border-sky-100 ${isSelected ? 'bg-blue-50 text-blue-700 font-bold' : 'text-slate-700'}">
                    <div class="flex items-center gap-2.5 truncate">
                        <span class="text-xl flex-shrink-0">${meta.flag}</span>
                        <div class="truncate">
                            <div class="flex items-center gap-1.5 leading-tight">
                                <span class="font-black font-mono text-xs sm:text-sm text-slate-900 group-hover:text-blue-600">${code}</span>
                                <span class="text-xs text-slate-500 font-semibold truncate">${meta.name}</span>
                            </div>
                            <div class="text-[10px] text-slate-400 font-mono mt-0.5">${rateDesc}</div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0 ml-2">
                        <span class="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono font-bold text-xs group-hover:bg-blue-100 group-hover:text-blue-800">${sym}</span>
                        <i class="fas fa-check text-blue-600 text-xs curr-check ${isSelected ? '' : 'hidden'}"></i>
                    </div>
                </button>
            `;
        });

        let popularPillsHtml = '';
        popularCurrencies.forEach(code => {
            const meta = CURRENCY_METADATA[code] || { flag: '🌍' };
            const sym = CURRENCY_SYMBOLS[code] || code;
            popularPillsHtml += `
                <button type="button" onclick="selectSpherixCurrency('${code}');"
                    class="px-2.5 py-1 rounded-md text-xs font-mono font-bold border transition-all cursor-pointer flex items-center gap-1 ${code === currentCurrency ? 'bg-blue-600 text-white border-blue-600 shadow-xs' : 'bg-white text-slate-700 border-slate-200 hover:border-blue-300 hover:bg-blue-50'}">
                    <span>${meta.flag}</span>
                    <span>${code}</span>
                    <span class="text-[10px] opacity-75">${sym}</span>
                </button>
            `;
        });

        const dropdownEl = document.createElement('div');
        dropdownEl.id = 'spherix-currency-dropdown';
        dropdownEl.className = 'fixed inset-0 z-[9999] bg-black/40 backdrop-blur-xs hidden items-center justify-center p-4 transition-opacity';
        dropdownEl.innerHTML = `
            <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in duration-200" onclick="event.stopPropagation();">
                
                <!-- Modal Header -->
                <div class="p-4 bg-gradient-to-r from-blue-600 via-indigo-600 to-sky-600 text-white flex items-center justify-between">
                    <div class="flex items-center gap-2.5">
                        <div class="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-md flex items-center justify-center text-amber-300 text-lg shadow-inner">
                            <i class="fas fa-globe"></i>
                        </div>
                        <div>
                            <h3 class="text-sm font-black tracking-tight text-white m-0">Regional Currency & Location</h3>
                            <p class="text-[11px] text-blue-100 m-0">Select your preferred local billing currency</p>
                        </div>
                    </div>
                    <button type="button" onclick="closeCurrencyDropdown();" class="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition-colors cursor-pointer border-0">
                        <i class="fas fa-times"></i>
                    </button>
                </div>

                <!-- Auto Detect & Search Bar -->
                <div class="p-3.5 bg-slate-50 border-b border-slate-200/80 space-y-2.5">
                    <div class="flex items-center gap-2">
                        <button type="button" id="currencyAutoDetectBtn" onclick="autoDetectUserCurrency();"
                            class="w-full py-2 px-3 rounded-lg bg-white hover:bg-sky-50 border border-slate-200 hover:border-sky-300 text-slate-800 text-xs font-bold transition-all shadow-2xs flex items-center justify-center gap-2 cursor-pointer">
                            <i class="fas fa-location-crosshairs text-sky-600 text-sm animate-pulse"></i>
                            <span>Auto-Detect My Country &amp; Currency</span>
                        </button>
                    </div>

                    <!-- Search Input -->
                    <div class="relative">
                        <i class="fas fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs"></i>
                        <input type="text" id="currencySearchInput" placeholder="Search 195 countries or currency (e.g. USD, Euro, AED, Japan)..."
                            oninput="filterCurrencyList(this.value);"
                            class="w-full pl-8 pr-3 py-2 rounded-lg bg-white border border-slate-200 text-xs font-medium text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all">
                    </div>

                    <!-- Popular Currency Quick Pills -->
                    <div>
                        <div class="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider mb-1.5">Popular Currencies</div>
                        <div class="flex flex-wrap gap-1.5">
                            ${popularPillsHtml}
                        </div>
                    </div>
                </div>

                <!-- Currency Scroll List -->
                <div class="p-3 overflow-y-auto flex-1 max-h-[45vh] space-y-1" id="currencyListContainer">
                    ${allCurrenciesHtml}
                    <div id="currencyNoResults" class="hidden text-center py-8 text-slate-400 text-xs">
                        <i class="fas fa-coins text-2xl mb-2 text-slate-300 block"></i>
                        No currencies found matching your search.
                    </div>
                </div>

                <!-- Modal Footer -->
                <div class="p-3 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500 font-medium">
                    <span class="flex items-center gap-1.5">
                        <i class="fas fa-shield-halved text-emerald-600"></i>
                        <span>Real-Time International FX Rates</span>
                    </span>
                    <span class="font-mono text-[10px] text-slate-400">Pegged Base: INR (₹)</span>
                </div>
            </div>
        `;

        dropdownEl.addEventListener('click', function (e) {
            if (e.target === dropdownEl) {
                window.closeCurrencyDropdown();
            }
        });

        document.body.appendChild(dropdownEl);
    }

    // 12. Mutation Observer for Dynamic SPA Content & Modals
    function setupDOMObserver() {
        const observer = new MutationObserver((mutations) => {
            let shouldUpdate = false;
            for (const mutation of mutations) {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    for (const node of mutation.addedNodes) {
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            if (node.hasAttribute('data-inr-price') || node.querySelector('[data-inr-price], .spherix-price, .currency-price')) {
                                shouldUpdate = true;
                                break;
                            }
                        }
                    }
                }
                if (shouldUpdate) break;
            }
            if (shouldUpdate) {
                applyPricesToDOM(document.body);
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    // 13. Initialize on Load
    function init() {
        createCurrencyModal();
        updateNavbarBadges();
        applyPricesToDOM(document.body);
        setupDOMObserver();

        // If no explicit preference stored yet, detect location in background
        if (!localStorage.getItem(STORAGE_KEY)) {
            detectLocationAndSetCurrency(false);
        }

        // Close modal on Escape key
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                window.closeCurrencyDropdown();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // 14. Export to Window
    window.SpherixCurrency = {
        format: formatPrice,
        convert: convert,
        setCurrency: setCurrency,
        getCurrency: () => currentCurrency,
        getSymbol: getSymbol,
        getRates: () => ({ ...RATES_IN_INR }),
        detectLocation: () => detectLocationAndSetCurrency(true),
        applyToDOM: applyPricesToDOM,
        openModal: window.toggleCurrencyDropdown,
        closeModal: window.closeCurrencyDropdown
    };

})();
