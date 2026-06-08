interface PlaceholderPageProps {
  title: string;
  description: string;
}

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <section className="placeholder-panel">
      <p className="placeholder-kicker">Planned route</p>
      <h3>{title}</h3>
      <p className="panel-message">{description}</p>
    </section>
  );
}
