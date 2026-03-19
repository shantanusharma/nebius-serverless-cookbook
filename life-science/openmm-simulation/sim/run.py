import os
import sys
import argparse
from openmm import app, unit

from .utils import (
    create_simulation_directory, 
    download_pdb, 
    clean_structure,
    setup_simulation,
    run_simulation_steps
)
from .metadata import save_simulation_metadata
from .storage import upload_results_to_s3, check_s3_configuration
from .visualization import create_visualizations


def run_md_simulation(
    protein_id: str,
    steps: int,
    pdb_cache_dir: str | None = None,
) -> None:
    """
    Run a molecular dynamics simulation for a given protein structure.

    Args:
        protein_id: 4-character Protein Data Bank identifier (e.g., "1UBQ").
        steps: Number of integration steps to run (> 0).
        pdb_cache_dir: Optional path to PDB file cache directory.
    """
    try:
        # 0. Create simulation directory
        sim_dir = create_simulation_directory(protein_id)
        
        # 1. Download PDB if needed
        pdb_file, pdb_source = download_pdb(protein_id, sim_dir, pdb_cache_dir=pdb_cache_dir)
        print(f"PDB source: {pdb_source}")
        
        # 2. Clean structure (remove water, add hydrogens)
        topology, positions = clean_structure(pdb_file, protein_id, sim_dir)
        
        # 3. Setup force field and add hydrogens
        print(f"Setting up simulation for {protein_id}...")
        forcefield = app.ForceField('amber14-all.xml', 'implicit/gbn2.xml')
        
        print("Adding missing hydrogen atoms...")
        modeller = app.Modeller(topology, positions)
        try:
            modeller.addHydrogens(forcefield)
            print("Successfully added hydrogens")
            topology = modeller.topology
            positions = modeller.positions
            # Save exact topology used for simulation so MDTraj can
            # reliably load the generated DCD trajectory.
            simulation_topology_file = sim_dir / f"{protein_id}_simulation_topology.pdb"
            with open(simulation_topology_file, "w") as f:
                app.PDBFile.writeFile(topology, positions, f)
            print(f"Saved simulation topology to {simulation_topology_file}")
        except Exception as e:
            print(f"Warning: Could not add hydrogens automatically: {e}")
            print("Proceeding without adding hydrogens...")
        
        # 4. Setup OpenMM simulation
        system, integrator, simulation = setup_simulation(topology, positions, forcefield)
        simulation.context.setPositions(positions)
        
        # 5. Minimize energy (skip in container)
        print("Minimizing energy...")
        if os.path.exists('/.dockerenv'):
            print("Running in container - skipping energy minimization for stability")
        else:
            simulation.minimizeEnergy(maxIterations=1000)
            print("Energy minimization completed")

        # 6. Set initial velocities
        simulation.context.setVelocitiesToTemperature(300*unit.kelvin)
        
        # 7. Run simulation
        output_filename = sim_dir / f'{protein_id}_trajectory.dcd'
        log_filename = sim_dir / f'{protein_id}_simulation.log'
        
        run_simulation_steps(simulation, steps, output_filename, log_filename)
        
        # 8. Save metadata to file
        save_simulation_metadata(protein_id, steps, sim_dir, 
                                system, integrator, simulation, str(output_filename))

        # 9. Generate visualizations (non-fatal)
        try:
            create_visualizations(sim_dir, protein_id)
        except Exception as e:
            print(f"Warning: Visualization generation failed: {e}")
            print("Continuing without plots.")
        
        # 10. Upload results to cloud storage
        upload_results_to_s3(sim_dir)
            
    except Exception as e:
        print(f"Simulation failed: {e}")
        import traceback
        traceback.print_exc()
        raise

def main() -> None:
    """
    Command line interface for running simulations.

    Supports both positional and named arguments:
      - Positional: python -m sim.run 1UBQ 1000
      - Named:      python -m sim.run --protein-id 1UBQ --steps 1000
      - Mixed:      python -m sim.run 1UBQ --steps 1000
    """
    parser = argparse.ArgumentParser(
        prog="python -m sim.run",
        description="Run a simple OpenMM MD simulation"
    )

    # Backward-compatible optional positionals
    parser.add_argument("protein_id", nargs="?", help="Protein ID (e.g., 1UBQ)")
    parser.add_argument("steps", nargs="?", type=int, help="Number of MD steps to run")

    # Preferred named arguments
    parser.add_argument("--protein-id", dest="protein_id_named", help="Protein ID (e.g., 1UBQ)")
    parser.add_argument("--steps", dest="steps_named", type=int, help="Number of MD steps to run")
    parser.add_argument("--pdb-cache-dir", dest="pdb_cache_dir", default=None,
                        help="Path to local PDB file cache (default: assets/pdb)")

    args = parser.parse_args(sys.argv[1:])

    protein_id_arg = args.protein_id_named if args.protein_id_named is not None else args.protein_id
    steps_arg = args.steps_named if args.steps_named is not None else args.steps

    if protein_id_arg is None or steps_arg is None:
        parser.error("protein_id and steps are required. Provide as positionals or with --protein-id and --steps.")

    print(f"Starting MD simulation for {protein_id_arg} with {steps_arg} steps")
    run_md_simulation(
        protein_id=protein_id_arg,
        steps=int(steps_arg),
        pdb_cache_dir=args.pdb_cache_dir,
    )
    print("Simulation complete!")

if __name__ == "__main__":
    main()