import { useState } from 'react';
import { Group } from './types';
import { GroupPanel } from './GroupPanel';

export interface BoardPanelProps {
	report: { groups: Group[]; summary: { runs: number; failure_groups: number; failed_job_minutes: number; flaky_candidates: number } };
	selected: Group | null;
	setSelected: (group: Group | null) => void;
	editable: boolean;
	exportReport: (format: string) => void;
}

export function BoardPanel({ report, selected, setSelected, editable, exportReport }: BoardPanelProps) {
	const [hovered, setHovered] = useState<Group | null>(null);

	return (
		<section className="panel">
			<div className="section-head">
				<h2>Prioritized failures</h2>
				<div className="actions">
					{['json', 'csv', 'markdown'].map(x => (
						<button className="secondary" key={x} onClick={() => exportReport(x)}>
							{x.toUpperCase()}
						</button>
					))}
				</div>
			</div>
			<p>{report.summary.failure_groups} failure signatures · {report.summary.failed_job_minutes} failed job minutes</p>
			<div className="groups-list">
				{report.groups.map(group => (
					<div
						key={group.id}
						className={selected?.id === group.id ? 'group-item selected' : 'group-item'}
						onClick={() => setSelected(group)}
						title={`View details for ${group.job}`}
						onMouseOver={() => setHovered(group)}
						onMouseOut={() => setHovered(null)}
					>
						<strong>{group.job}</strong>
						{group.test && <span>/ {group.test}</span>}
						<small>{group.repository} · {group.workflow}</small>
					</div>
				))}
			</div>
		</section>
	);
}
