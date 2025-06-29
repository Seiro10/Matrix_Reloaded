#!/usr/bin/env python3
"""
Dashboard HIL Centralisé
Permet d'interagir avec tous les agents depuis un terminal centralisé
Ajout du support pour la sélection de mots-clés
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import Dict, Any, List
import threading
import sys
import os
from queue import Queue
import signal


class HILDashboard:
    def __init__(self):
        self.agents = {
            "content-finder": "http://localhost:8000",
            "router-agent": "http://localhost:8080",
            "copywriter-agent": "http://localhost:8083",
            "metadata-generator": "http://localhost:8084",
            "rewriter-main": "http://localhost:8085"
        }

        self.pending_validations = {}
        self.validation_queue = Queue()
        self.running = True

        # Colors for terminal
        self.COLORS = {
            'RED': '\033[0;31m',
            'GREEN': '\033[0;32m',
            'YELLOW': '\033[1;33m',
            'BLUE': '\033[0;34m',
            'MAGENTA': '\033[0;35m',
            'CYAN': '\033[0;36m',
            'WHITE': '\033[1;37m',
            'RESET': '\033[0m'
        }

    def colored(self, text: str, color: str) -> str:
        """Add color to text"""
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['RESET']}"

    def log(self, message: str, color: str = 'WHITE'):
        """Log with timestamp and color"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"{self.colored(f'[{timestamp}]', 'CYAN')} {self.colored(message, color)}")

    async def check_agent_health(self, name: str, url: str) -> bool:
        """Check if an agent is healthy"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/health", timeout=5) as response:
                    return response.status == 200
        except:
            return False

    async def monitor_agents(self):
        """Monitor all agents continuously"""
        while self.running:
            try:
                # Check agent health
                agent_status = {}
                for name, url in self.agents.items():
                    is_healthy = await self.check_agent_health(name, url)
                    agent_status[name] = "🟢" if is_healthy else "🔴"

                # Check for pending validations from router-agent
                await self.check_pending_validations_router()

                # Check for pending validations from content-finder
                await self.check_pending_validations_content_finder()

                # Sleep before next check
                await asyncio.sleep(10)

            except Exception as e:
                self.log(f"Error in monitoring: {e}", 'RED')
                await asyncio.sleep(5)

    async def check_pending_validations_router(self):
        """Check for pending validations from router-agent"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.agents['router-agent']}/pending-validations") as response:
                    if response.status == 200:
                        data = await response.json()
                        pending = data.get("pending_validations", [])

                        for validation in pending:
                            validation_id = validation["validation_id"]
                            if validation_id not in self.pending_validations:
                                # New validation from router
                                validation["source_agent"] = "router-agent"
                                self.pending_validations[validation_id] = validation
                                self.validation_queue.put(validation)

        except Exception as e:
            pass  # Ignore connection errors

    async def check_pending_validations_content_finder(self):
        """Check for pending validations from content-finder"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.agents['content-finder']}/pending-validations") as response:
                    if response.status == 200:
                        data = await response.json()
                        pending = data.get("pending_validations", [])

                        for validation in pending:
                            validation_id = validation["validation_id"]
                            if validation_id not in self.pending_validations:
                                # New validation from content-finder
                                validation["source_agent"] = "content-finder"
                                self.pending_validations[validation_id] = validation
                                self.validation_queue.put(validation)

        except Exception as e:
            pass  # Ignore connection errors

    async def submit_validation_response(self, validation_id: str, response: str,
                                         source_agent: str = "router-agent") -> bool:
        """Submit validation response to the appropriate agent"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "validation_id": validation_id,
                    "response": response
                }

                agent_url = self.agents[source_agent]
                async with session.post(
                        f"{agent_url}/submit-validation",
                        json=payload
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            self.log(f"Error submitting validation: {e}", 'RED')
            return False

    async def continue_workflow(self, validation_id: str, source_agent: str = "router-agent") -> Dict[str, Any]:
        """Continue workflow after validation"""
        try:
            async with aiohttp.ClientSession() as session:
                agent_url = self.agents[source_agent]
                async with session.post(
                        f"{agent_url}/continue-workflow/{validation_id}"
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        return {"error": f"HTTP {resp.status}"}
        except Exception as e:
            return {"error": str(e)}

    async def execute_action(self, validation_id: str, source_agent: str = "router-agent") -> Dict[str, Any]:
        """Execute final action"""
        try:
            async with aiohttp.ClientSession() as session:
                agent_url = self.agents[source_agent]
                async with session.post(
                        f"{agent_url}/execute-action/{validation_id}"
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        return {"error": f"HTTP {resp.status}"}
        except Exception as e:
            return {"error": str(e)}

    async def continue_keyword_selection_workflow(self, validation_id: str, selected_keyword: str) -> Dict[str, Any]:
        """Continue content-finder workflow after keyword selection"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"selected_keyword": selected_keyword}
                async with session.post(
                        f"{self.agents['content-finder']}/continue-with-keyword/{validation_id}",
                        json=payload
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        return {"error": f"HTTP {resp.status}"}
        except Exception as e:
            return {"error": str(e)}

    def display_header(self):
        """Display dashboard header"""
        os.system('clear' if os.name == 'posix' else 'cls')
        print("=" * 80)
        print(self.colored("🎛️  DASHBOARD HIL CENTRALISÉ - AGENTS CONTENT", 'WHITE'))
        print("=" * 80)
        print()

        # Show agent status
        print(self.colored("📡 ÉTAT DES AGENTS:", 'CYAN'))
        for name, url in self.agents.items():
            port = url.split(':')[-1]
            print(f"  {name:<20} (:{port}) - En vérification...")
        print()

    def display_validation_request(self, validation_data: Dict[str, Any]):
        """Display validation request in a nice format"""
        data = validation_data["data"]
        source_agent = validation_data.get("source_agent", "router-agent")

        if data["type"] == "keyword_selection":
            # NEW: Keyword selection display
            print(self.colored("🔍 SÉLECTION DE MOT-CLÉ PRINCIPAL", 'YELLOW'))
            print("=" * 50)
            print(f"Agent: {self.colored('Content-Finder', 'MAGENTA')}")

            keywords = data.get('keywords', [])
            keyword_data = data.get('keyword_data', {})

            print(f"Mots-clés disponibles: {self.colored(str(len(keywords)), 'WHITE')}")
            print()

            # Show each keyword with its metrics
            for i, keyword in enumerate(keywords[:10], 1):
                kw_data = keyword_data.get(keyword, {})
                competition = kw_data.get('competition', 'UNKNOWN')
                monthly_searches = kw_data.get('monthly_searches', 0)

                print(f"{self.colored(f'{i:2d}.', 'CYAN')} {self.colored(keyword, 'WHITE')}")
                print(f"     Volume: {self.colored(str(monthly_searches), 'GREEN')} | "
                      f"Concurrence: {self.colored(competition, 'BLUE')}")

            print()

        elif data["type"] == "routing_approval":
            # Existing routing approval display
            print(self.colored("🤔 DEMANDE DE VALIDATION", 'YELLOW'))
            print("=" * 50)
            print(f"Agent: {self.colored('Router-Agent', 'MAGENTA')}")
            print(f"Keyword: {self.colored(data.get('keyword', 'N/A'), 'WHITE')}")
            print(f"Site sélectionné: {self.colored(data.get('selected_site', 'N/A'), 'GREEN')}")
            print(f"Décision: {self.colored(data.get('routing_decision', 'N/A'), 'BLUE')}")
            print(f"Confiance: {self.colored(data.get('confidence_score', 'N/A'), 'CYAN')}")

            if data.get('existing_content_found'):
                print(f"Contenu existant: {self.colored('✅ Trouvé', 'GREEN')}")
                if data.get('best_match_title'):
                    print(f"Meilleur match: {data['best_match_title']}")
            else:
                print(f"Contenu existant: {self.colored('❌ Non trouvé', 'RED')}")

            print()
            print("Raisonnement:")
            reasoning = data.get('reasoning', '').strip()
            for line in reasoning.split('\n'):
                if line.strip():
                    print(f"  {line.strip()}")
            print()

    def get_user_input(self, prompt: str, options: List[str]) -> str:
        """Get user input with validation"""
        while True:
            try:
                response = input(f"{prompt} ({'/'.join(options)}): ").strip().lower()
                if response in [opt.lower() for opt in options]:
                    return response
                print(f"Veuillez choisir parmi: {', '.join(options)}")
            except KeyboardInterrupt:
                return "stop"
            except EOFError:
                return "stop"

    def get_keyword_selection(self, keywords: List[str]) -> str:
        """Get keyword selection from user"""
        while True:
            try:
                print(self.colored(f"Options disponibles:", 'CYAN'))
                print(f"  • Tapez un numéro (1-{len(keywords[:10])})")
                print(f"  • Tapez 'stop' pour arrêter")
                print()

                selection = input(
                    self.colored(f"Votre choix: ", 'YELLOW')
                ).strip()

                if selection.lower() in ['stop', 'quit', 'exit']:
                    return "stop"

                try:
                    selection_num = int(selection)
                    if 1 <= selection_num <= len(keywords[:10]):
                        return keywords[selection_num - 1]
                    else:
                        print(f"❌ Veuillez choisir entre 1 et {len(keywords[:10])}")
                        continue
                except ValueError:
                    print("❌ Veuillez entrer un numéro valide ou 'stop'")
                    continue

            except KeyboardInterrupt:
                return "stop"
            except EOFError:
                return "stop"

    async def handle_validation(self, validation_data: Dict[str, Any]):
        """Handle a validation request interactively"""
        validation_id = validation_data["validation_id"]
        data = validation_data["data"]
        source_agent = validation_data.get("source_agent", "router-agent")

        # Display the request
        self.display_validation_request(validation_data)

        if data["type"] == "keyword_selection":
            # NEW: Handle keyword selection
            keywords = data.get("keywords", [])

            selected_keyword = self.get_keyword_selection(keywords)

            # Submit response
            success = await self.submit_validation_response(validation_id, selected_keyword, source_agent)

            if success:
                self.log(f"✅ Réponse envoyée: {selected_keyword}", 'GREEN')

                if selected_keyword != "stop":
                    # Continue workflow with selected keyword
                    self.log("🔄 Continuation du workflow avec le mot-clé sélectionné...", 'BLUE')
                    result = await self.continue_keyword_selection_workflow(validation_id, selected_keyword)

                    if result.get("success"):
                        self.log("✅ Workflow continué avec succès!", 'GREEN')

                        # Check if this triggers router-agent workflow
                        router_response = result.get("router_response")
                        if router_response and router_response.get("validation_required"):
                            new_validation_id = router_response["validation_id"]
                            self.log(f"🔄 Router-agent validation déclenchée: {new_validation_id}", 'BLUE')
                        elif router_response and router_response.get("success"):
                            self.log(f"✅ Processus complet terminé avec succès!", 'GREEN')
                    else:
                        self.log(f"❌ Erreur: {result.get('error', 'Unknown error')}", 'RED')
                else:
                    self.log("🛑 Processus arrêté par l'utilisateur", 'RED')
            else:
                self.log("❌ Erreur lors de l'envoi de la réponse", 'RED')

        elif data["type"] == "routing_approval":
            # Existing routing approval logic
            response = self.get_user_input(
                self.colored("Approuvez-vous cette décision de routage?", 'YELLOW'),
                ["yes", "no", "y", "n"]
            )

            # Normalize response
            if response in ["y", "yes"]:
                response = "yes"
            elif response in ["n", "no"]:
                response = "no"

            # Submit response
            success = await self.submit_validation_response(validation_id, response, source_agent)

            if success:
                self.log(f"✅ Réponse envoyée: {response}", 'GREEN')

                if response == "yes":
                    # Continue workflow
                    self.log("🔄 Continuation du workflow...", 'BLUE')
                    result = await self.continue_workflow(validation_id, source_agent)

                    if "validation_required" in result:
                        # Another validation needed (no good URL found)
                        new_validation_id = result["validation_id"]
                        self.log(f"⏳ Nouvelle validation requise: {new_validation_id}", 'YELLOW')
                        # The monitoring loop will pick this up
                    elif result.get("auto_executed"):
                        # Workflow was auto-executed with suggested URL
                        self.log("✅ Workflow exécuté automatiquement avec URL suggérée!", 'GREEN')

                        agent_response = result.get("agent_response", {})
                        if agent_response and agent_response.get("success"):
                            self.log(f"📝 Réponse agent: {agent_response.get('message', 'N/A')}", 'CYAN')
                        elif agent_response:
                            self.log(f"⚠️ Erreur agent: {agent_response.get('error', 'N/A')}", 'YELLOW')
                    else:
                        # Normal completion
                        self.log("✅ Workflow terminé", 'GREEN')
                else:
                    self.log("🛑 Processus arrêté par l'utilisateur", 'RED')

        elif data["type"] == "action_choice":
            # Existing action choice logic
            options = data.get("options", ["copywriter", "stop"])
            response = self.get_user_input(
                self.colored("Quelle action souhaitez-vous prendre?", 'YELLOW'),
                options
            )

            # Submit response
            success = await self.submit_validation_response(validation_id, response, source_agent)

            if success:
                self.log(f"✅ Action choisie: {response}", 'GREEN')

                if response != "stop":
                    # Execute action
                    self.log("🔄 Exécution de l'action...", 'BLUE')
                    result = await self.execute_action(validation_id, source_agent)

                    if result.get("success"):
                        self.log("✅ Action exécutée avec succès!", 'GREEN')

                        agent_response = result.get("agent_response", {})
                        if agent_response.get("success"):
                            self.log(f"📝 Réponse agent: {agent_response.get('message', 'N/A')}", 'CYAN')
                        else:
                            self.log(f"⚠️ Erreur agent: {agent_response.get('error', 'N/A')}", 'YELLOW')
                    else:
                        self.log(f"❌ Erreur: {result.get('error', 'Unknown error')}", 'RED')
                else:
                    self.log("🛑 Processus arrêté par l'utilisateur", 'RED')
            else:
                self.log("❌ Erreur lors de l'envoi de la réponse", 'RED')

        # Clean up
        if validation_id in self.pending_validations:
            del self.pending_validations[validation_id]

        print()
        input(self.colored("Appuyez sur Entrée pour continuer...", 'CYAN'))

    def run_input_handler(self):
        """Handle user input in a separate thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while self.running:
                try:
                    # Check for new validations
                    if not self.validation_queue.empty():
                        validation_data = self.validation_queue.get()
                        loop.run_until_complete(self.handle_validation(validation_data))
                    else:
                        time.sleep(1)
                except Exception as e:
                    print(f"Error in input handler: {e}")
                    time.sleep(1)
        finally:
            loop.close()

    async def run_dashboard(self):
        """Run the main dashboard"""
        self.display_header()

        print(self.colored("🚀 Démarrage du dashboard HIL...", 'GREEN'))
        print(self.colored("💡 Le dashboard surveille automatiquement les demandes de validation", 'CYAN'))
        print(self.colored("🔍 Support ajouté pour la sélection de mots-clés", 'BLUE'))
        print(self.colored("🛑 Ctrl+C pour quitter", 'YELLOW'))
        print()

        # Start input handler in separate thread
        input_thread = threading.Thread(target=self.run_input_handler, daemon=True)
        input_thread.start()

        # Start monitoring
        try:
            await self.monitor_agents()
        except KeyboardInterrupt:
            self.log("🛑 Arrêt du dashboard...", 'YELLOW')
            self.running = False

    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        self.running = False
        print(f"\n{self.colored('🛑 Arrêt du dashboard...', 'YELLOW')}")
        sys.exit(0)


async def main():
    """Main function"""
    dashboard = HILDashboard()

    # Handle Ctrl+C
    signal.signal(signal.SIGINT, dashboard.signal_handler)

    await dashboard.run_dashboard()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Dashboard arrêté")
        sys.exit(0)