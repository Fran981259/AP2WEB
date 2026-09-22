export const FLAGS = {
  Spain: '🇪🇸', England: '🏴󠁧󠁢󠁥󠁮󠁧󠁿', Germany: '🇩🇪', Italy: '🇮🇹', France: '🇫🇷',
  Portugal: '🇵🇹', Netherlands: '🇳🇱', Belgium: '🇧🇪', Argentina: '🇦🇷',
  Brazil: '🇧🇷', Australia: '🇦🇺', Belarus: '🇧🇾', USA: '🇺🇸', Mexico: '🇲🇽',
  Colombia: '🇨🇴', Chile: '🇨🇱', Uruguay: '🇺🇾', Peru: '🇵🇪', Ecuador: '🇪🇨',
  Paraguay: '🇵🇾', Bolivia: '🇧🇴', Venezuela: '🇻🇪', Japan: '🇯🇵', China: '🇨🇳',
  Turkey: '🇹🇷', Greece: '🇬🇷', Russia: '🇷🇺', Ukraine: '🇺🇦', Poland: '🇵🇱',
  Switzerland: '🇨🇭', Austria: '🇦🇹', Scotland: '🏴󠁧󠁢󠁳󠁣󠁴󠁿', Ireland: '🇮🇪',
  Denmark: '🇩🇰', Sweden: '🇸🇪', Norway: '🇳🇴', Finland: '🇫🇮', Canada: '🇨🇦',
  'South Korea': '🇰🇷', 'Saudi Arabia': '🇸🇦', Qatar: '🇶🇦', Egypt: '🇪🇬', Croatia: '🇭🇷',
  Serbia: '🇷🇸', Romania: '🇷🇴', Czech: '🇨🇿', Slovakia: '🇸🇰', Hungary: '🇭🇺',
  India: '🇮🇳', Vietnam: '🇻🇳', 'South Africa': '🇿🇦', Iceland: '🇮🇸', Latvia: '🇱🇻',
  Bulgaria: '🇧🇬', Israel: '🇮🇱', Slovenia: '🇸🇮', Wales: '🏴󠁧󠁢󠁷󠁬󠁳󠁿', 'Northern Ireland': '🇬🇧',
  Malta: '🇲🇹', Panama: '🇵🇦',
}

export function flag(country) {
  if (!country) return '🏆'
  return FLAGS[country] || FLAGS[country.split(' ')[0]] || '🏆'
}

export const CONTINENTS = {
  Brazil: 'América do Sul', Argentina: 'América do Sul', Chile: 'América do Sul',
  Uruguay: 'América do Sul', Peru: 'América do Sul', Ecuador: 'América do Sul',
  Paraguay: 'América do Sul', Bolivia: 'América do Sul', Venezuela: 'América do Sul',
  Colombia: 'América do Sul',
  USA: 'América do Norte', Mexico: 'América do Norte', Canada: 'América do Norte',
  Spain: 'Europa', England: 'Europa', Germany: 'Europa', Italy: 'Europa',
  France: 'Europa', Portugal: 'Europa', Netherlands: 'Europa', Belgium: 'Europa',
  Turkey: 'Europa', Greece: 'Europa', Russia: 'Europa', Ukraine: 'Europa',
  Poland: 'Europa', Switzerland: 'Europa', Austria: 'Europa', Scotland: 'Europa',
  Ireland: 'Europa', Denmark: 'Europa', Sweden: 'Europa', Norway: 'Europa',
  Finland: 'Europa', Croatia: 'Europa', Serbia: 'Europa', Romania: 'Europa',
  Czech: 'Europa', Slovakia: 'Europa', Hungary: 'Europa', Belarus: 'Europa',
  Bulgaria: 'Europa', Israel: 'Ásia', Slovenia: 'Europa', Iceland: 'Europa',
  Latvia: 'Europa', Wales: 'Europa', 'Northern Ireland': 'Europa', Malta: 'Europa',
  India: 'Ásia', Vietnam: 'Ásia', 'South Africa': 'África',
  Panama: 'América do Norte',
  Japan: 'Ásia', China: 'Ásia', 'South Korea': 'Ásia', 'Saudi Arabia': 'Ásia',
  Qatar: 'Ásia',
  Egypt: 'África',
  Australia: 'Oceania',
}

export const CONTINENT_ORDER = ['Europa', 'América do Sul', 'América do Norte', 'Ásia', 'África', 'Oceania', 'Outros']

export function continent(country) {
  if (!country) return 'Outros'
  return CONTINENTS[country] || CONTINENTS[country.split(' ')[0]] || 'Outros'
}
