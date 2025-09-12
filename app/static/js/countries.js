// Liste des pays avec codes ISO et noms français
const COUNTRIES = {
    'AD': 'Andorre',
    'AE': 'Émirats arabes unis',
    'AF': 'Afghanistan', 
    'AG': 'Antigua-et-Barbuda',
    'AI': 'Anguilla',
    'AL': 'Albanie',
    'AM': 'Arménie',
    'AO': 'Angola',
    'AR': 'Argentine',
    'AT': 'Autriche',
    'AU': 'Australie',
    'AW': 'Aruba',
    'AZ': 'Azerbaïdjan',
    'BA': 'Bosnie-Herzégovine',
    'BB': 'Barbade',
    'BD': 'Bangladesh',
    'BE': 'Belgique',
    'BF': 'Burkina Faso',
    'BG': 'Bulgarie',
    'BH': 'Bahreïn',
    'BI': 'Burundi',
    'BJ': 'Bénin',
    'BM': 'Bermudes',
    'BN': 'Brunéi',
    'BO': 'Bolivie',
    'BR': 'Brésil',
    'BS': 'Bahamas',
    'BT': 'Bhoutan',
    'BW': 'Botswana',
    'BY': 'Biélorussie',
    'BZ': 'Belize',
    'CA': 'Canada',
    'CD': 'République démocratique du Congo',
    'CF': 'République centrafricaine',
    'CG': 'République du Congo',
    'CH': 'Suisse',
    'CI': 'Côte d\'Ivoire',
    'CL': 'Chili',
    'CM': 'Cameroun',
    'CN': 'Chine',
    'CO': 'Colombie',
    'CR': 'Costa Rica',
    'CU': 'Cuba',
    'CV': 'Cap-Vert',
    'CY': 'Chypre',
    'CZ': 'République tchèque',
    'DE': 'Allemagne',
    'DJ': 'Djibouti',
    'DK': 'Danemark',
    'DM': 'Dominique',
    'DO': 'République dominicaine',
    'DZ': 'Algérie',
    'EC': 'Équateur',
    'EE': 'Estonie',
    'EG': 'Égypte',
    'ER': 'Érythrée',
    'ES': 'Espagne',
    'ET': 'Éthiopie',
    'FI': 'Finlande',
    'FJ': 'Fidji',
    'FM': 'Micronésie',
    'FR': 'France',
    'GA': 'Gabon',
    'GB': 'Royaume-Uni',
    'GD': 'Grenade',
    'GE': 'Géorgie',
    'GH': 'Ghana',
    'GM': 'Gambie',
    'GN': 'Guinée',
    'GQ': 'Guinée équatoriale',
    'GR': 'Grèce',
    'GT': 'Guatemala',
    'GW': 'Guinée-Bissau',
    'GY': 'Guyana',
    'HN': 'Honduras',
    'HR': 'Croatie',
    'HT': 'Haïti',
    'HU': 'Hongrie',
    'ID': 'Indonésie',
    'IE': 'Irlande',
    'IL': 'Israël',
    'IN': 'Inde',
    'IQ': 'Irak',
    'IR': 'Iran',
    'IS': 'Islande',
    'IT': 'Italie',
    'JM': 'Jamaïque',
    'JO': 'Jordanie',
    'JP': 'Japon',
    'KE': 'Kenya',
    'KG': 'Kirghizistan',
    'KH': 'Cambodge',
    'KI': 'Kiribati',
    'KM': 'Comores',
    'KN': 'Saint-Christophe-et-Niévès',
    'KP': 'Corée du Nord',
    'KR': 'Corée du Sud',
    'KW': 'Koweït',
    'KZ': 'Kazakhstan',
    'LA': 'Laos',
    'LB': 'Liban',
    'LC': 'Sainte-Lucie',
    'LI': 'Liechtenstein',
    'LK': 'Sri Lanka',
    'LR': 'Libéria',
    'LS': 'Lesotho',
    'LT': 'Lituanie',
    'LU': 'Luxembourg',
    'LV': 'Lettonie',
    'LY': 'Libye',
    'MA': 'Maroc',
    'MC': 'Monaco',
    'MD': 'Moldavie',
    'ME': 'Monténégro',
    'MG': 'Madagascar',
    'MH': 'Îles Marshall',
    'MK': 'Macédoine du Nord',
    'ML': 'Mali',
    'MM': 'Myanmar',
    'MN': 'Mongolie',
    'MR': 'Mauritanie',
    'MT': 'Malte',
    'MU': 'Maurice',
    'MV': 'Maldives',
    'MW': 'Malawi',
    'MX': 'Mexique',
    'MY': 'Malaisie',
    'MZ': 'Mozambique',
    'NA': 'Namibie',
    'NE': 'Niger',
    'NG': 'Nigéria',
    'NI': 'Nicaragua',
    'NL': 'Pays-Bas',
    'NO': 'Norvège',
    'NP': 'Népal',
    'NR': 'Nauru',
    'NZ': 'Nouvelle-Zélande',
    'OM': 'Oman',
    'PA': 'Panama',
    'PE': 'Pérou',
    'PG': 'Papouasie-Nouvelle-Guinée',
    'PH': 'Philippines',
    'PK': 'Pakistan',
    'PL': 'Pologne',
    'PS': 'Palestine',
    'PT': 'Portugal',
    'PW': 'Palaos',
    'PY': 'Paraguay',
    'QA': 'Qatar',
    'RO': 'Roumanie',
    'RS': 'Serbie',
    'RU': 'Russie',
    'RW': 'Rwanda',
    'SA': 'Arabie saoudite',
    'SB': 'Îles Salomon',
    'SC': 'Seychelles',
    'SD': 'Soudan',
    'SE': 'Suède',
    'SG': 'Singapour',
    'SI': 'Slovénie',
    'SK': 'Slovaquie',
    'SL': 'Sierra Leone',
    'SM': 'Saint-Marin',
    'SN': 'Sénégal',
    'SO': 'Somalie',
    'SR': 'Suriname',
    'SS': 'Soudan du Sud',
    'ST': 'São Tomé-et-Principe',
    'SV': 'Salvador',
    'SY': 'Syrie',
    'SZ': 'Eswatini',
    'TD': 'Tchad',
    'TG': 'Togo',
    'TH': 'Thaïlande',
    'TJ': 'Tadjikistan',
    'TL': 'Timor oriental',
    'TM': 'Turkménistan',
    'TN': 'Tunisie',
    'TO': 'Tonga',
    'TR': 'Turquie',
    'TT': 'Trinité-et-Tobago',
    'TV': 'Tuvalu',
    'TW': 'Taïwan',
    'TZ': 'Tanzanie',
    'UA': 'Ukraine',
    'UG': 'Ouganda',
    'US': 'États-Unis',
    'UY': 'Uruguay',
    'UZ': 'Ouzbékistan',
    'VA': 'Vatican',
    'VC': 'Saint-Vincent-et-les Grenadines',
    'VE': 'Venezuela',
    'VN': 'Viêt Nam',
    'VU': 'Vanuatu',
    'WS': 'Samoa',
    'YE': 'Yémen',
    'ZA': 'Afrique du Sud',
    'ZM': 'Zambie',
    'ZW': 'Zimbabwe'
};

// Fonction pour créer un sélecteur de pays
function createCountrySelector(selectedCountries = []) {
    const selector = document.createElement('div');
    selector.className = 'country-selector';
    
    const search = document.createElement('input');
    search.type = 'text';
    search.placeholder = 'Rechercher un pays...';
    search.className = 'country-search';
    
    const list = document.createElement('div');
    list.className = 'country-list';
    list.style.display = 'none';
    
    const selectedList = document.createElement('div');
    selectedList.className = 'selected-countries';
    
    // Créer la liste des pays
    Object.entries(COUNTRIES)
        .sort(([,a], [,b]) => a.localeCompare(b))
        .forEach(([code, name]) => {
            const item = document.createElement('div');
            item.className = 'country-item';
            item.dataset.code = code;
            item.innerHTML = `<span class="country-flag">${getFlagEmoji(code)}</span> ${name}`;
            item.addEventListener('click', () => selectCountry(code, name));
            list.appendChild(item);
        });
    
    // Affichage des pays sélectionnés
    function updateSelectedCountries() {
        selectedList.innerHTML = '';
        selectedCountries.forEach(code => {
            const tag = document.createElement('span');
            tag.className = 'country-tag';
            tag.innerHTML = `
                <span class="country-flag">${getFlagEmoji(code)}</span>
                ${COUNTRIES[code]}
                <button type="button" onclick="removeCountry('${code}')">&times;</button>
            `;
            selectedList.appendChild(tag);
        });
        
        // Cacher les pays déjà sélectionnés
        list.querySelectorAll('.country-item').forEach(item => {
            const code = item.dataset.code;
            item.style.display = selectedCountries.includes(code) ? 'none' : 'block';
        });
    }
    
    function selectCountry(code, name) {
        if (selectedCountries.length >= 3) {
            alert('Maximum 3 nationalités autorisées');
            return;
        }
        
        if (!selectedCountries.includes(code)) {
            selectedCountries.push(code);
            updateSelectedCountries();
            search.value = '';
            list.style.display = 'none';
        }
    }
    
    // Fonction globale pour supprimer un pays
    window.removeCountry = function(code) {
        const index = selectedCountries.indexOf(code);
        if (index > -1) {
            selectedCountries.splice(index, 1);
            updateSelectedCountries();
        }
    };
    
    // Events de recherche
    search.addEventListener('focus', () => {
        list.style.display = 'block';
    });
    
    search.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        list.querySelectorAll('.country-item').forEach(item => {
            const text = item.textContent.toLowerCase();
            const match = text.includes(query);
            const alreadySelected = selectedCountries.includes(item.dataset.code);
            item.style.display = (match && !alreadySelected) ? 'block' : 'none';
        });
        list.style.display = 'block';
    });
    
    // Fermer la liste en cliquant dehors
    document.addEventListener('click', (e) => {
        if (!selector.contains(e.target)) {
            list.style.display = 'none';
        }
    });
    
    selector.appendChild(search);
    selector.appendChild(list);
    selector.appendChild(selectedList);
    
    // Initialiser avec les pays sélectionnés
    updateSelectedCountries();
    
    // Méthode pour récupérer les pays sélectionnés
    selector.getSelectedCountries = () => selectedCountries;
    
    return selector;
}

// Helper pour les drapeaux emoji
function getFlagEmoji(countryCode) {
    return String.fromCodePoint(
        ...[...countryCode.toUpperCase()].map(x => 0x1f1a5 + x.charCodeAt())
    );
}