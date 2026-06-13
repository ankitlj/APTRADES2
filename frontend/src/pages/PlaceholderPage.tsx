import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/common/page";

interface PlaceholderPageProps {
  title: string;
  description: string;
}

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4">
      <PageHeader kicker="Planned route" title={title} />
      <Card>
        <CardContent className="p-6">
          <p className="text-sm text-muted-foreground">{description}</p>
        </CardContent>
      </Card>
    </div>
  );
}
