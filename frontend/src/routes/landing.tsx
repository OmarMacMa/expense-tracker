import { Button } from '@/components/ui/button';
import { BarChart3, Shield, Users } from 'lucide-react';

export default function Landing() {
  const handleSignIn = () => {
    window.location.href = '/api/v1/auth/google';
  };

  return (
    <div className="min-h-screen bg-[#FAFAFE]">
      {/* Hero section */}
      <div className="flex flex-col items-center justify-center px-4 pt-24 pb-16 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-[#1D1B20] md:text-5xl">
          Expense Tracker
        </h1>
        <p className="mt-4 max-w-md text-lg text-[#615D69]">
          Track shared expenses with your partner or family. See where your
          money goes, set limits, and stay on budget together.
        </p>
        <Button
          onClick={handleSignIn}
          className="mt-8 rounded-xl bg-[#7C6FA0] px-8 py-6 text-lg font-medium text-white hover:bg-[#6B5F8A]"
        >
          Sign in with Google
        </Button>
      </div>

      {/* Feature cards */}
      <div className="mx-auto max-w-3xl px-4 pb-24">
        <div className="grid gap-6 md:grid-cols-3">
          <FeatureCard
            icon={<Users className="h-6 w-6 text-[#7C6FA0]" />}
            title="Shared Spaces"
            description="Track expenses together in a shared space. Everyone sees the full picture."
          />
          <FeatureCard
            icon={<BarChart3 className="h-6 w-6 text-[#8BA89A]" />}
            title="Smart Insights"
            description="See spending trends, category breakdowns, and how you compare to your average."
          />
          <FeatureCard
            icon={<Shield className="h-6 w-6 text-[#A0889C]" />}
            title="Budget Limits"
            description="Set weekly or monthly limits and get alerts before you overspend."
          />
        </div>
      </div>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div
      className="rounded-xl bg-white p-6"
      style={{
        boxShadow:
          '0 2px 12px rgba(29,27,32,0.04), 0 6px 24px rgba(29,27,32,0.03)',
      }}
    >
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-[#F3F1F8]">
        {icon}
      </div>
      <h3 className="text-lg font-medium text-[#1D1B20]">{title}</h3>
      <p className="mt-2 text-sm text-[#615D69]">{description}</p>
    </div>
  );
}
