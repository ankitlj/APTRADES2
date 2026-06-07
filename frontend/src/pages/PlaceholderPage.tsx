interface PlaceholderPageProps {
  title: string;
  description: string;
}

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <section className="panel">
      <p className="eyebrow">Planned route</p>
      <h3>{title}</h3>
      <p className="panel-copy">{description}</p>
    </section>
  );
}
