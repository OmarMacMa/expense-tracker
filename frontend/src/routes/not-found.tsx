import { Link } from 'react-router';
import { Button } from '@/components/ui/button';

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#FAFAFE] px-4">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-[#7C6FA0]">404</h1>
        <p className="mt-4 text-lg text-[#1D1B20]">Page not found</p>
        <p className="mt-2 text-sm text-[#615D69]">
          The page you're looking for doesn't exist.
        </p>
        <Link to="/home">
          <Button className="mt-6 bg-[#7C6FA0] hover:bg-[#6B5F8A]">
            Go to Dashboard
          </Button>
        </Link>
      </div>
    </div>
  );
}
