import { Link } from "react-router-dom";
import { User, MapPin } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import type { Patient } from "@/services/patientService";

export function PatientCard({ patient }: { patient: Patient }) {
  const initials = patient.name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <Link to={`/patients/${patient.id}`}>
      <Card glass className="transition-transform hover:-translate-y-0.5 hover:shadow-md">
        <CardContent className="flex items-center gap-4 p-5">
          <Avatar className="h-12 w-12">
            {patient.photo_path && <AvatarImage src={patient.photo_path} alt={patient.name} />}
            <AvatarFallback>{initials || <User className="h-5 w-5" />}</AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold">{patient.name}</p>
            <p className="text-xs text-muted-foreground">
              {patient.age ? `${patient.age} yrs` : "Age N/A"} · {patient.gender ?? "N/A"}
            </p>
            {patient.room_number && (
              <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                <MapPin className="h-3 w-3" /> Room {patient.room_number}
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
