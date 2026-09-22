export const METHOD_META = {
  bayesian: { icon: '🧠', label: 'Bayesiano' },
  hybrid: { icon: '⚖️', label: 'Híbrido' },
  poisson: { icon: '🎲', label: 'Poisson' },
}

export const CTX_META = [
  ['ctx_rest', '😴 descanso'],
  ['ctx_form', '📈 forma'],
  ['ctx_team_ha', '🏟️ mando'],
]

export const STAT_LABELS = {
  xg: 'xG', xg_on_target: 'xG no alvo', possession: 'Posse',
  shots_total: 'Chutes', shots_on_target: 'No gol', shots_off_target: 'Fora',
  shots_inside_box: 'Na área', shots_outside_box: 'Fora área', blocked_shots: 'Bloqueados',
  big_chances: 'Grandes chances', big_chances_missed: 'Chances perdidas',
  corners: 'Escanteios', fouls: 'Faltas', yellow_cards: 'Amarelos', red_cards: 'Vermelhos',
  passes: 'Passes', accurate_passes: 'Passes certos', offsides: 'Impedimentos',
  saves: 'Defesas', interceptions: 'Interceptações', recoveries: 'Recuperações',
  tackles: 'Desarmes', dribbles: 'Dribles', duels: 'Duelos', aerial_duels: 'Duelos aéreos',
  final_third: 'Final 1/3', throw_ins: 'Laterais', goal_kicks: 'Tiros de meta',
}
