import * as React from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Activity, Lock, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { PulseLine } from "@/components/layout/PulseLine";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/ui/toast";
import * as authService from "@/services/authService";

export default function Login() {
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [showForgotPassword, setShowForgotPassword] = React.useState(false);

  const { login } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch {
      setError("Incorrect email or password.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleForgotPassword = async () => {
    if (!email) {
      setError("Enter your email above first, then click 'Forgot password'.");
      return;
    }
    await authService.forgotPassword(email);
    toast({ title: "Reset link sent", description: "Check your email if an account exists for that address.", variant: "success" });
    setShowForgotPassword(false);
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4">
      <div className="absolute inset-0 -z-10 bg-gradient-to-br from-primary/5 via-background to-accent/5" />

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <Card glass className="w-full max-w-md">
          <CardContent className="p-8">
            <div className="mb-6 flex flex-col items-center text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
                <Activity className="h-6 w-6" />
              </div>
              <h1 className="font-display text-2xl font-bold">MobilityWatch</h1>
              <p className="text-sm text-muted-foreground">AI-based patient mobility monitoring</p>
              <PulseLine className="mt-4 h-6 w-40 text-accent/50" />
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    required
                    autoComplete="email"
                    placeholder="you@hospital.com"
                    className="pl-9"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="password"
                    type="password"
                    required
                    autoComplete="current-password"
                    placeholder="••••••••"
                    className="pl-9"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}

              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Signing in..." : "Sign in"}
              </Button>

              <button
                type="button"
                onClick={handleForgotPassword}
                className="w-full text-center text-xs text-muted-foreground hover:text-primary"
              >
                {showForgotPassword ? "Sending..." : "Forgot password?"}
              </button>
            </form>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
