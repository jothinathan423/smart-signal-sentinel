
import React from "react";
import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Home, BarChart, Info, Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

const Navigation = () => {
  const location = useLocation();
  const [open, setOpen] = React.useState(false);

  const routes = [
    {
      name: "Home",
      path: "/",
      icon: <Home className="h-5 w-5" />,
    },
    {
      name: "Dashboard",
      path: "/dashboard",
      icon: <BarChart className="h-5 w-5" />,
    },
    {
      name: "About",
      path: "/about",
      icon: <Info className="h-5 w-5" />,
    },
  ];

  const NavLink = ({ route }: { route: typeof routes[0] }) => {
    const isActive = location.pathname === route.path;

    return (
      <Link
        to={route.path}
        className={cn(
          "flex items-center gap-2 px-3 py-2 rounded-lg transition-all duration-200",
          isActive
            ? "bg-primary text-primary-foreground"
            : "text-foreground/70 hover:bg-accent hover:text-foreground"
        )}
        onClick={() => setOpen(false)}
      >
        {route.icon}
        <span>{route.name}</span>
      </Link>
    );
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="mr-2 flex items-center space-x-2">
            <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center">
              <div className="h-3 w-3 rounded-full bg-primary-foreground" />
            </div>
            <span className="font-semibold hidden md:inline-block">Smart Traffic</span>
          </div>
          <nav className="hidden md:flex items-center gap-1">
            {routes.map((route) => (
              <NavLink key={route.path} route={route} />
            ))}
          </nav>
        </div>

        <div className="md:hidden">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden">
                <Menu className="h-5 w-5" />
                <span className="sr-only">Toggle navigation menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[300px] sm:w-[400px]">
              <div className="flex items-center gap-2 mb-8">
                <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center">
                  <div className="h-3 w-3 rounded-full bg-primary-foreground" />
                </div>
                <span className="font-semibold">Smart Traffic</span>
              </div>
              <nav className="flex flex-col gap-2">
                {routes.map((route) => (
                  <NavLink key={route.path} route={route} />
                ))}
              </nav>
            </SheetContent>
          </Sheet>
        </div>

        <div>
          <Button size="sm" variant="outline" className="hidden md:flex">
            Version 1.0
          </Button>
        </div>
      </div>
    </header>
  );
};

export default Navigation;
