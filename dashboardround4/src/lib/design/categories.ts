// Nave Design System — glass categorical palette
export interface Cat {
	id: string;
	label: string;
	color: string;
}

export const CATS: Cat[] = [
	{ id: 'residential', label: 'Residential', color: '#ee8434' },
	{ id: 'other_christian', label: 'Other Christian use', color: '#496ddb' },
	{ id: 'education', label: 'Education', color: '#717ec3' },
	{ id: 'hospitality', label: 'Hospitality', color: '#c95d63' },
	{ id: 'commercial', label: 'Commercial', color: '#a20021' },
	{ id: 'community', label: 'Community', color: '#f52f57' },
	{ id: 'arts_culture', label: 'Arts & Culture', color: '#f3752b' },
	{ id: 'unknown', label: 'Other / unrecorded', color: '#ae8799' }
];

const SHORT_LABEL: Record<string, string> = {
	residential: 'Residential',
	other_christian: 'Christian',
	education: 'Education',
	hospitality: 'Hospitality',
	commercial: 'Commercial',
	community: 'Community',
	arts_culture: 'Arts',
	unknown: 'Other'
};

export function catColor(id: string | null | undefined): string {
	return CATS.find((c) => c.id === id)?.color ?? '#ae8799';
}

export function catLabel(id: string | null | undefined): string {
	return CATS.find((c) => c.id === id)?.label ?? 'Other';
}

export function catShortLabel(id: string | null | undefined): string {
	return (id && SHORT_LABEL[id]) || 'Other';
}

export const DENSITY_RAMP = ['#3a1c08', '#7a3d12', '#b35d1f', '#ee8434', '#f79d5c'];

export function densityColor(d: number): string {
	return DENSITY_RAMP[Math.min(4, Math.floor(d * 5))];
}
